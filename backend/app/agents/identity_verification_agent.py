"""
Identity Verification Agent (consolidated)

Consolidates all prior pipeline results into a final identity determination:
  - OCR match scores from the verification agent
  - Document quality and tampering flags
  - Compliance status and flags
  - Government identity validation score
  - Duplicate detection

Produces a consolidated identity confidence score and a verified/unverified/
inconclusive status.

Output fields written to state:
  identity_verification_status    : verified | unverified | inconclusive
  identity_confidence_score       : float 0.0-1.0
  fraud_flag                      : bool
  identity_verification_summary   : str
  identity_verification_details   : dict
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Weights for consolidated confidence score
# ---------------------------------------------------------------------------
# These weights sum to 1.0 and reflect relative importance in final decision

WEIGHTS = {
    "ocr_name_match": 0.20,
    "government_match": 0.30,
    "document_quality": 0.15,
    "document_completeness": 0.10,
    "compliance_clean": 0.15,
    "no_fraud_flags": 0.10,
}

VERIFIED_THRESHOLD = 0.78
UNVERIFIED_THRESHOLD = 0.45

# Flags that immediately force fraud_flag=True regardless of score
CRITICAL_FRAUD_FLAGS = {
    "DUPLICATE_SUBMISSION",
    "SANCTIONS_MATCH_FOUND",
    "TAMPERING_SUSPECTED",
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compliance_score(compliance_status: Optional[str], compliance_flags: Optional[List[str]]) -> float:
    """Convert compliance status to a 0.0-1.0 score."""
    if compliance_status == "passed":
        return 1.0
    if compliance_status == "flagged":
        num_flags = len(compliance_flags or [])
        return max(0.30, 1.0 - 0.20 * num_flags)
    return 0.0  # failed


def _build_consolidated_score(
    name_score: Optional[float],
    gov_score: Optional[float],
    doc_quality: Optional[float],
    doc_completeness: Optional[float],
    compliance_status: Optional[str],
    compliance_flags: Optional[List[str]],
    fraud_flags: Optional[List[str]],
) -> float:
    """Compute weighted consolidated identity confidence score."""
    components = {
        "ocr_name_match": name_score or 0.0,
        "government_match": gov_score or 0.0,
        "document_quality": doc_quality or 0.5,
        "document_completeness": doc_completeness or 0.5,
        "compliance_clean": _compliance_score(compliance_status, compliance_flags),
        "no_fraud_flags": max(0.0, 1.0 - len(fraud_flags or []) * 0.15),
    }

    score = sum(WEIGHTS[k] * v for k, v in components.items())
    return round(score, 4)


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def identity_verification_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: consolidate all prior results into final identity decision.

    Reads:
        state["name_match_score"], state["dob_match"], state["id_match"]
        state["duplicate_detected"], state["fraud_flags"]
        state["document_quality_score"], state["document_completeness_score"]
        state["document_tampering_flag"]
        state["compliance_status"], state["compliance_flags"]
        state["government_match_score"], state["government_validation_status"]

    Writes:
        state["identity_verification_status"]
        state["identity_confidence_score"]
        state["fraud_flag"]
        state["identity_verification_summary"]
        state["identity_verification_details"]
        state["current_agent"]
    """
    submission_id = state.get("kyc_submission_id", "unknown")
    logger.info("Identity Verification agent started", submission_id=submission_id)

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "identity_verification_agent"

    try:
        name_score = state.get("name_match_score")
        dob_match = state.get("dob_match")
        id_match = state.get("id_match")
        duplicate = state.get("duplicate_detected") or False
        fraud_flags: List[str] = state.get("fraud_flags") or []

        doc_quality = state.get("document_quality_score")
        doc_completeness = state.get("document_completeness_score")
        tampering = state.get("document_tampering_flag") or False

        compliance_status = state.get("compliance_status")
        compliance_flags: List[str] = state.get("compliance_flags") or []

        gov_score = state.get("government_match_score")
        gov_status = state.get("government_validation_status")

        # Aggregate fraud flags from all sources
        all_fraud_indicators: List[str] = list(fraud_flags)
        if tampering:
            all_fraud_indicators.append("TAMPERING_SUSPECTED")
        if "SANCTIONS_MATCH_FOUND" in compliance_flags:
            all_fraud_indicators.append("SANCTIONS_MATCH_FOUND")
        if duplicate:
            all_fraud_indicators.append("DUPLICATE_SUBMISSION")

        # Deduplicate
        all_fraud_indicators = list(dict.fromkeys(all_fraud_indicators))

        # Determine fraud_flag
        has_critical = any(f in CRITICAL_FRAUD_FLAGS for f in all_fraud_indicators)
        fraud_flag = has_critical or len(all_fraud_indicators) >= 3

        # Consolidated confidence score
        identity_confidence = _build_consolidated_score(
            name_score=name_score,
            gov_score=gov_score,
            doc_quality=doc_quality,
            doc_completeness=doc_completeness,
            compliance_status=compliance_status,
            compliance_flags=compliance_flags,
            fraud_flags=all_fraud_indicators,
        )

        # Determine status
        if fraud_flag or identity_confidence < UNVERIFIED_THRESHOLD:
            status = "unverified"
        elif identity_confidence >= VERIFIED_THRESHOLD:
            status = "verified"
        else:
            status = "inconclusive"

        # Build summary
        summary_parts = [
            f"Identity verification {status}.",
            f"Consolidated confidence: {identity_confidence:.0%}.",
        ]
        if gov_status:
            summary_parts.append(f"Government validation: {gov_status}.")
        if fraud_flag:
            summary_parts.append(f"Fraud indicators: {', '.join(all_fraud_indicators)}.")
        elif not all_fraud_indicators:
            summary_parts.append("No fraud indicators detected.")
        if compliance_status:
            summary_parts.append(f"Compliance: {compliance_status}.")

        summary = " ".join(summary_parts)

        details = {
            "components": {
                "name_match_score": name_score,
                "dob_match": dob_match,
                "id_match": id_match,
                "document_quality_score": doc_quality,
                "document_completeness_score": doc_completeness,
                "document_tampering": tampering,
                "compliance_status": compliance_status,
                "government_match_score": gov_score,
                "government_status": gov_status,
                "duplicate_detected": duplicate,
            },
            "fraud_indicators": all_fraud_indicators,
            "weights_used": WEIGHTS,
            "thresholds": {
                "verified": VERIFIED_THRESHOLD,
                "unverified": UNVERIFIED_THRESHOLD,
            },
        }

        new_state.update({
            "identity_verification_status": status,
            "identity_confidence_score": identity_confidence,
            "fraud_flag": fraud_flag,
            "identity_verification_summary": summary,
            "identity_verification_details": details,
            # Propagate identity confidence as the primary confidence score
            "confidence_score": identity_confidence,
        })

        logger.info(
            "Identity Verification agent completed",
            submission_id=submission_id,
            status=status,
            confidence=identity_confidence,
            fraud_flag=fraud_flag,
        )

    except Exception as exc:
        logger.error(
            "Identity Verification agent failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        new_state.update({
            "identity_verification_status": "inconclusive",
            "identity_confidence_score": 0.0,
            "fraud_flag": False,
            "identity_verification_summary": f"Identity verification failed: {exc}",
            "identity_verification_details": {"error": str(exc)},
        })

    return new_state
