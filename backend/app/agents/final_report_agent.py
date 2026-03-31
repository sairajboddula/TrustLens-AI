"""
Final Report Generation Agent

Generates a comprehensive structured KYC report for admin review.
Collects all prior agent outputs and organizes them into a single
structured report document.

The report includes:
  - Customer submitted details
  - OCR extracted details
  - Per-agent workflow results (all 5 review stages)
  - Fraud / compliance flags
  - Final confidence score
  - Recommended action

Persists the report to the KYCFinalReport DB table so admins can
retrieve it via the API.

Output fields written to state:
  final_report            : dict (complete report)
  final_recommendation    : str (approve | reject | manual_review)
  report_generated_at     : str (ISO 8601)
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Recommendation thresholds (mirrors decision_agent for report preview)
# ---------------------------------------------------------------------------
APPROVE_THRESHOLD = 0.78
REJECT_THRESHOLD = 0.45


# ---------------------------------------------------------------------------
# Report builder
# ---------------------------------------------------------------------------


def _build_report(state: KYCAgentState, generated_at: str) -> Dict[str, Any]:
    """Construct the full structured KYC report from state."""
    form_data: Dict[str, Any] = state.get("form_data") or {}

    return {
        "report_metadata": {
            "submission_id": state.get("kyc_submission_id"),
            "generated_at": generated_at,
            "report_version": "1.0",
            "pipeline_version": "admin-review-v2",
        },
        "customer_submitted_details": {
            "first_name": form_data.get("first_name"),
            "last_name": form_data.get("last_name"),
            "date_of_birth": form_data.get("date_of_birth"),
            "nationality": form_data.get("nationality"),
            "address": form_data.get("address"),
            "phone": form_data.get("phone"),
            "email": form_data.get("email"),
            "id_type": form_data.get("id_type"),
            "id_number": form_data.get("id_number"),
        },
        "ocr_extracted_details": {
            "extracted_name": state.get("extracted_name"),
            "extracted_dob": state.get("extracted_dob"),
            "extracted_id_number": state.get("extracted_id_number"),
            "extracted_address": state.get("extracted_address"),
            "ocr_document_count": len(state.get("ocr_results") or []),
        },
        "workflow_results": {
            "document_analysis": {
                "status": state.get("document_analysis_status"),
                "quality_score": state.get("document_quality_score"),
                "completeness_score": state.get("document_completeness_score"),
                "tampering_flag": state.get("document_tampering_flag"),
                "document_type": state.get("document_type_detected"),
                "summary": state.get("document_analysis_summary"),
            },
            "compliance_review": {
                "status": state.get("compliance_status"),
                "flags": state.get("compliance_flags") or [],
                "pep_result": state.get("pep_result"),
                "sanctions_result": state.get("sanctions_result"),
                "summary": state.get("compliance_summary"),
            },
            "government_validation": {
                "status": state.get("government_validation_status"),
                "match_score": state.get("government_match_score"),
                "reference_id": state.get("government_reference_id"),
                "summary": state.get("government_validation_summary"),
            },
            "identity_verification": {
                "status": state.get("identity_verification_status"),
                "confidence_score": state.get("identity_confidence_score"),
                "fraud_flag": state.get("fraud_flag"),
                "name_match_score": state.get("name_match_score"),
                "dob_match": state.get("dob_match"),
                "id_match": state.get("id_match"),
                "duplicate_detected": state.get("duplicate_detected"),
                "summary": state.get("identity_verification_summary"),
            },
        },
        "fraud_compliance_flags": {
            "fraud_flags": state.get("fraud_flags") or [],
            "compliance_flags": state.get("compliance_flags") or [],
            "fraud_detected": state.get("fraud_flag") or False,
            "tampering_detected": state.get("document_tampering_flag") or False,
        },
        "scores_summary": {
            "final_confidence_score": state.get("identity_confidence_score"),
            "name_match_score": state.get("name_match_score"),
            "document_quality_score": state.get("document_quality_score"),
            "government_match_score": state.get("government_match_score"),
        },
    }


def _determine_recommendation(
    confidence: Optional[float],
    fraud_flag: Optional[bool],
    compliance_status: Optional[str],
) -> str:
    """Determine the recommended action based on consolidated scores."""
    confidence = confidence or 0.0

    if fraud_flag or compliance_status == "failed":
        return "reject"

    if confidence >= APPROVE_THRESHOLD and compliance_status == "passed":
        return "approve"
    elif confidence < REJECT_THRESHOLD:
        return "reject"
    else:
        return "manual_review"


# ---------------------------------------------------------------------------
# DB persistence
# ---------------------------------------------------------------------------


def _persist_report(
    submission_id: str,
    report: Dict[str, Any],
    recommendation: str,
    confidence: Optional[float],
    state: KYCAgentState,
) -> None:
    """Persist the final report to the DB."""
    from sqlalchemy import select  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.workflow import KYCFinalReport  # noqa: PLC0415

    async def _save():
        async with AsyncSessionLocal() as session:
            # Upsert: delete old report if exists, then insert
            existing = await session.execute(
                select(KYCFinalReport).where(KYCFinalReport.submission_id == submission_id)
            )
            old = existing.scalar_one_or_none()
            if old:
                await session.delete(old)
                await session.flush()

            new_report = KYCFinalReport(
                submission_id=submission_id,
                report_data=report,
                final_confidence_score=confidence,
                recommended_action=recommendation,
                fraud_detected=state.get("fraud_flag") or False,
                compliance_passed=(state.get("compliance_status") == "passed"),
                government_validated=(state.get("government_validation_status") == "verified"),
                identity_verified=(state.get("identity_verification_status") == "verified"),
                document_quality_score=state.get("document_quality_score"),
                document_tampered=state.get("document_tampering_flag") or False,
                generated_at=datetime.now(timezone.utc),
            )
            session.add(new_report)
            await session.commit()

    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures  # noqa: PLC0415
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _save())
                future.result(timeout=15)
        except RuntimeError:
            asyncio.run(_save())
    except Exception as exc:
        logger.error(
            "Final Report agent: DB persistence failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def final_report_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: generate and persist the final KYC report.

    Reads: all prior agent outputs from state.

    Writes:
        state["final_report"]
        state["final_recommendation"]
        state["report_generated_at"]
        state["current_agent"]
    """
    submission_id = state.get("kyc_submission_id", "unknown")
    logger.info("Final Report agent started", submission_id=submission_id)

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "final_report_agent"

    try:
        generated_at = datetime.now(timezone.utc).isoformat()

        report = _build_report(state, generated_at)

        confidence = state.get("identity_confidence_score")
        fraud_flag = state.get("fraud_flag")
        compliance_status = state.get("compliance_status")

        recommendation = _determine_recommendation(confidence, fraud_flag, compliance_status)
        report["recommended_action"] = recommendation

        # Persist to DB (non-blocking shim)
        _persist_report(
            submission_id=state.get("kyc_submission_id", ""),
            report=report,
            recommendation=recommendation,
            confidence=confidence,
            state=state,
        )

        new_state.update({
            "final_report": report,
            "final_recommendation": recommendation,
            "report_generated_at": generated_at,
        })

        logger.info(
            "Final Report agent completed",
            submission_id=submission_id,
            recommendation=recommendation,
            confidence=confidence,
        )

    except Exception as exc:
        logger.error(
            "Final Report agent failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        new_state.update({
            "final_report": {"error": str(exc)},
            "final_recommendation": "manual_review",
            "report_generated_at": datetime.now(timezone.utc).isoformat(),
        })

    return new_state
