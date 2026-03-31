"""
Customer Document Analysis Agent

Analyzes uploaded customer documents after OCR to assess:
  - Document type detection
  - Completeness of mandatory fields
  - Image / document quality scoring
  - Suspicious / tampering indicators

Uses lightweight heuristics on the OCR results already present in state.
All logic is demo-safe and production-structured.

Output fields written to state:
  document_analysis_status       : completed | failed | skipped
  document_quality_score         : float 0.0-1.0
  document_tampering_flag        : bool
  document_type_detected         : str
  document_completeness_score    : float 0.0-1.0
  document_analysis_summary      : str
  document_analysis_details      : dict
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Tampering heuristics: these keywords in OCR text may indicate tampering
# ---------------------------------------------------------------------------
TAMPER_KEYWORDS = [
    "invalid", "void", "cancelled", "specimen", "duplicate",
    "copy", "not valid", "sample", "test document",
]

# Expected mandatory fields per document type (keys in extracted OCR text)
MANDATORY_FIELDS: Dict[str, List[str]] = {
    "passport": ["name", "date", "number", "nationality", "expiry"],
    "national_id": ["name", "date", "number", "address"],
    "drivers_license": ["name", "date", "number", "address"],
    "residence_permit": ["name", "date", "number"],
    "default": ["name", "date", "number"],
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _detect_document_type(form_data: Dict[str, Any], ocr_text: str) -> str:
    """Return detected document type, preferring the form-declared type."""
    declared = (form_data.get("id_type") or "").lower()
    if declared in ("passport", "national_id", "drivers_license", "residence_permit"):
        return declared
    # Fallback: keyword detection from OCR text
    lower_text = ocr_text.lower()
    if "passport" in lower_text:
        return "passport"
    if "driving" in lower_text or "licence" in lower_text or "license" in lower_text:
        return "drivers_license"
    if "national" in lower_text and "id" in lower_text:
        return "national_id"
    if "permit" in lower_text or "residence" in lower_text:
        return "residence_permit"
    return "unknown"


def _assess_quality(ocr_results: List[Dict[str, Any]]) -> float:
    """
    Derive a quality score from OCR confidence and text length.

    A confidence above 0.80 and sufficient text → score near 1.0.
    Low confidence or very short OCR text → lower score.
    """
    if not ocr_results:
        return 0.40  # no OCR data – neutral/low

    confidences = [r.get("confidence", 0.5) for r in ocr_results if r.get("confidence") is not None]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0.5

    text_lengths = [len(r.get("raw_text") or "") for r in ocr_results]
    total_chars = sum(text_lengths)

    # Length component: ≥200 chars is "good", normalize to [0, 1]
    length_score = min(total_chars / 200.0, 1.0)

    quality = round(0.60 * avg_conf + 0.40 * length_score, 4)
    return quality


def _detect_tampering(ocr_text: str, form_data: Dict[str, Any]) -> bool:
    """
    Detect potential tampering indicators.

    Checks:
    1. Blacklisted keywords in OCR text.
    2. Expiry date in the past by more than 10 years (possible old/fake doc).
    """
    lower = ocr_text.lower()
    for keyword in TAMPER_KEYWORDS:
        if keyword in lower:
            logger.warning("Tampering keyword detected in OCR text", keyword=keyword)
            return True

    # Check expiry from form data
    expiry_str = form_data.get("document_expiry")
    if expiry_str:
        try:
            expiry_dt = datetime.strptime(str(expiry_str)[:10], "%Y-%m-%d")
            age_years = (datetime.now() - expiry_dt).days / 365.25
            if age_years > 10:
                logger.warning("Document expired more than 10 years ago", expiry=expiry_str)
                return True
        except (ValueError, TypeError):
            pass

    return False


def _assess_completeness(
    extracted_name: Optional[str],
    extracted_dob: Optional[str],
    extracted_id: Optional[str],
    doc_type: str,
) -> float:
    """
    Score how complete the extracted fields are (0.0 - 1.0).

    Weights mandatory fields by document type.
    """
    field_present = {
        "name": bool(extracted_name),
        "date": bool(extracted_dob),
        "number": bool(extracted_id),
    }
    mandatory = MANDATORY_FIELDS.get(doc_type, MANDATORY_FIELDS["default"])
    found = sum(1 for f in mandatory if field_present.get(f, False))
    # Only count the 3 we track; cap to mandatory list size
    countable = min(len(mandatory), 3)
    return round(found / countable, 4) if countable > 0 else 0.0


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def customer_document_analysis_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: analyse document quality and completeness.

    Reads:
        state["ocr_results"], state["form_data"]
        state["extracted_name"], state["extracted_dob"], state["extracted_id_number"]

    Writes:
        state["document_analysis_status"]
        state["document_quality_score"]
        state["document_tampering_flag"]
        state["document_type_detected"]
        state["document_completeness_score"]
        state["document_analysis_summary"]
        state["document_analysis_details"]
        state["current_agent"]
    """
    submission_id = state.get("kyc_submission_id", "unknown")
    logger.info("Customer Document Analysis agent started", submission_id=submission_id)

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "customer_document_analysis_agent"

    ocr_results: List[Dict[str, Any]] = state.get("ocr_results") or []
    form_data: Dict[str, Any] = state.get("form_data") or {}

    # Combine all OCR text
    combined_text = " ".join(
        r.get("raw_text") or "" for r in ocr_results
    )

    try:
        # 1. Document type detection
        doc_type = _detect_document_type(form_data, combined_text)

        # 2. Quality scoring
        quality_score = _assess_quality(ocr_results)

        # 3. Tampering detection
        tampering = _detect_tampering(combined_text, form_data)
        if tampering:
            quality_score = max(0.0, quality_score - 0.20)  # penalty

        # 4. Completeness scoring
        completeness = _assess_completeness(
            extracted_name=state.get("extracted_name"),
            extracted_dob=state.get("extracted_dob"),
            extracted_id=state.get("extracted_id_number"),
            doc_type=doc_type,
        )

        # 5. Build summary
        flags = []
        if quality_score < 0.50:
            flags.append("LOW_QUALITY")
        if tampering:
            flags.append("TAMPERING_SUSPECTED")
        if completeness < 0.60:
            flags.append("INCOMPLETE_DOCUMENT")

        if not flags:
            summary = (
                f"Document analysis completed. Type: {doc_type}. "
                f"Quality: {quality_score:.0%}. Completeness: {completeness:.0%}. "
                "No suspicious indicators found."
            )
        else:
            summary = (
                f"Document analysis completed with flags: {', '.join(flags)}. "
                f"Type: {doc_type}. Quality: {quality_score:.0%}. "
                f"Completeness: {completeness:.0%}."
            )

        details = {
            "document_type": doc_type,
            "quality_score": quality_score,
            "completeness_score": completeness,
            "tampering_flag": tampering,
            "ocr_document_count": len(ocr_results),
            "flags": flags,
            "combined_text_length": len(combined_text),
        }

        new_state.update({
            "document_analysis_status": "completed",
            "document_quality_score": quality_score,
            "document_tampering_flag": tampering,
            "document_type_detected": doc_type,
            "document_completeness_score": completeness,
            "document_analysis_summary": summary,
            "document_analysis_details": details,
        })

        logger.info(
            "Customer Document Analysis agent completed",
            submission_id=submission_id,
            doc_type=doc_type,
            quality=quality_score,
            completeness=completeness,
            tampering=tampering,
        )

    except Exception as exc:
        logger.error(
            "Customer Document Analysis agent failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        new_state.update({
            "document_analysis_status": "failed",
            "document_analysis_summary": f"Document analysis failed: {exc}",
            "document_analysis_details": {"error": str(exc)},
        })

    return new_state
