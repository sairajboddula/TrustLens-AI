"""
KYC Decision Agent

Analyses the verification results (confidence score + fraud flags) and
produces a final decision: APPROVED | REJECTED | MANUAL_REVIEW.

Decision logic:
  - confidence >= 0.85 AND no fraud flags            → APPROVED
  - confidence <  0.50 OR critical fraud flag present → REJECTED
  - otherwise                                         → MANUAL_REVIEW

Risk levels:
  - confidence >= 0.80                                → LOW
  - confidence >= 0.60                                → MEDIUM
  - confidence >= 0.40                                → HIGH
  - confidence <  0.40                                → CRITICAL

After deciding, the agent updates the KYCSubmission record in the DB.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

APPROVE_THRESHOLD = 0.85
REJECT_THRESHOLD = 0.50

RISK_THRESHOLDS = [
    (0.80, "LOW"),
    (0.60, "MEDIUM"),
    (0.40, "HIGH"),
]

CRITICAL_FRAUD_FLAGS = {
    "DUPLICATE_SUBMISSION",
    "ID_FORMAT_INVALID",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _classify_risk(confidence: float) -> str:
    for threshold, level in RISK_THRESHOLDS:
        if confidence >= threshold:
            return level
    return "CRITICAL"


def _build_decision_reason(
    decision: str,
    confidence: float,
    fraud_flags: List[str],
    name_score: Optional[float],
    dob_match: Optional[bool],
    id_match: Optional[bool],
) -> str:
    """Compose a human-readable explanation of the decision."""
    lines: List[str] = [
        f"Decision: {decision}.",
        f"Overall confidence score: {confidence:.2%}.",
    ]

    if name_score is not None:
        lines.append(f"Name similarity score: {name_score:.2%}.")

    if dob_match is not None:
        lines.append(
            "Date of birth: " + ("matched" if dob_match else "did NOT match") + "."
        )

    if id_match is not None:
        lines.append(
            "ID number: " + ("matched" if id_match else "did NOT match") + "."
        )

    if fraud_flags:
        lines.append(f"Fraud flags detected: {', '.join(fraud_flags)}.")
    else:
        lines.append("No fraud flags detected.")

    if decision == "APPROVED":
        lines.append(
            "All verification checks passed with sufficient confidence. "
            "KYC application approved automatically."
        )
    elif decision == "REJECTED":
        if confidence < REJECT_THRESHOLD:
            lines.append(
                f"Confidence score ({confidence:.2%}) is below the rejection "
                f"threshold ({REJECT_THRESHOLD:.2%})."
            )
        critical = [f for f in fraud_flags if f in CRITICAL_FRAUD_FLAGS]
        if critical:
            lines.append(
                f"Critical fraud flag(s) present: {', '.join(critical)}."
            )
    else:
        lines.append(
            "Confidence score and/or verification results are inconclusive. "
            "Manual review by a KYC analyst is required."
        )

    return " ".join(lines)


def _update_db(submission_id: str, decision: str, risk_level: str, reason: str, state: KYCAgentState) -> None:
    """
    Persist the final decision to the KYCSubmission record.
    Runs as a sync shim (same pattern as other agents).
    """
    from sqlalchemy import select  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.kyc import KYCSubmission, KYCStatus, RiskLevel  # noqa: PLC0415

    # Map decision string → KYCStatus
    status_map = {
        "APPROVED": KYCStatus.APPROVED,
        "REJECTED": KYCStatus.REJECTED,
        "MANUAL_REVIEW": KYCStatus.UNDER_REVIEW,
    }
    risk_map = {
        "LOW": RiskLevel.LOW,
        "MEDIUM": RiskLevel.MEDIUM,
        "HIGH": RiskLevel.HIGH,
        "CRITICAL": RiskLevel.VERY_HIGH,
    }

    async def _persist():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KYCSubmission).where(KYCSubmission.id == submission_id)
            )
            submission = result.scalar_one_or_none()
            if submission is None:
                logger.warning(
                    "Decision agent: submission not found in DB",
                    submission_id=submission_id,
                )
                return

            now = datetime.now(timezone.utc)
            submission.status = status_map.get(decision, KYCStatus.UNDER_REVIEW)
            submission.status_reason = reason
            submission.risk_level = risk_map.get(risk_level, RiskLevel.HIGH)
            submission.ai_confidence_score = state.get("confidence_score")
            submission.ai_fraud_risk_score = 1.0 - (state.get("confidence_score") or 0.0)
            submission.ai_flags = state.get("fraud_flags") or []
            submission.processing_completed_at = now
            submission.langgraph_state = {
                "name_match_score": state.get("name_match_score"),
                "dob_match": state.get("dob_match"),
                "id_match": state.get("id_match"),
                "duplicate_detected": state.get("duplicate_detected"),
                "decision": decision,
                "risk_level": risk_level,
                "confidence_score": state.get("confidence_score"),
            }
            if decision == "REJECTED":
                flags = state.get("fraud_flags") or []
                submission.rejection_reasons = flags if flags else ["Low confidence score"]

            await session.commit()

    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _persist())
                future.result(timeout=15)
        except RuntimeError:
            asyncio.run(_persist())
    except Exception as exc:
        logger.error(
            "Decision agent: DB update failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def decision_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: produce the final KYC decision.

    Reads:
        state["confidence_score"]
        state["fraud_flags"]
        state["name_match_score"], state["dob_match"], state["id_match"]

    Writes:
        state["decision"]          – APPROVED | REJECTED | MANUAL_REVIEW
        state["risk_level"]        – LOW | MEDIUM | HIGH | CRITICAL
        state["decision_reason"]   – detailed explanation
        state["completed_at"]      – ISO 8601 timestamp
        state["processing_time_ms"]
        state["current_agent"]
    """
    logger.info(
        "Decision agent started",
        submission_id=state.get("kyc_submission_id"),
    )

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "decision_agent"

    confidence: float = state.get("confidence_score") or 0.0
    fraud_flags: List[str] = state.get("fraud_flags") or []
    has_critical_flag = bool(CRITICAL_FRAUD_FLAGS & set(fraud_flags))

    # -----------------------------------------------------------------------
    # Decision logic
    # -----------------------------------------------------------------------
    if confidence >= APPROVE_THRESHOLD and not fraud_flags:
        decision = "APPROVED"
    elif confidence < REJECT_THRESHOLD or has_critical_flag:
        decision = "REJECTED"
    else:
        decision = "MANUAL_REVIEW"

    risk_level = _classify_risk(confidence)

    decision_reason = _build_decision_reason(
        decision=decision,
        confidence=confidence,
        fraud_flags=fraud_flags,
        name_score=state.get("name_match_score"),
        dob_match=state.get("dob_match"),
        id_match=state.get("id_match"),
    )

    # -----------------------------------------------------------------------
    # Timing
    # -----------------------------------------------------------------------
    completed_at = datetime.now(timezone.utc).isoformat()
    processing_time_ms: Optional[int] = None
    started_at_str: Optional[str] = state.get("started_at")
    if started_at_str:
        try:
            started_dt = datetime.fromisoformat(started_at_str)
            completed_dt = datetime.fromisoformat(completed_at)
            # Make both timezone-aware or both naive for subtraction
            if started_dt.tzinfo is None:
                started_dt = started_dt.replace(tzinfo=timezone.utc)
            if completed_dt.tzinfo is None:
                completed_dt = completed_dt.replace(tzinfo=timezone.utc)
            processing_time_ms = int(
                (completed_dt - started_dt).total_seconds() * 1000
            )
        except Exception:
            pass

    # -----------------------------------------------------------------------
    # Persist to DB
    # -----------------------------------------------------------------------
    _update_db(
        submission_id=state.get("kyc_submission_id", ""),
        decision=decision,
        risk_level=risk_level,
        reason=decision_reason,
        state=new_state,
    )

    # -----------------------------------------------------------------------
    # Write back to state
    # -----------------------------------------------------------------------
    new_state["decision"] = decision
    new_state["risk_level"] = risk_level
    new_state["decision_reason"] = decision_reason
    new_state["completed_at"] = completed_at
    new_state["processing_time_ms"] = processing_time_ms

    logger.info(
        "Decision agent completed",
        submission_id=state.get("kyc_submission_id"),
        decision=decision,
        risk_level=risk_level,
        confidence=confidence,
        fraud_flags=fraud_flags,
        processing_time_ms=processing_time_ms,
    )

    return new_state
