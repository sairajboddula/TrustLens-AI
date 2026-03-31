"""
Fraud Detection Utilities

Provides helper functions for:
  - Fuzzy name similarity (RapidFuzz)
  - ID-number format validation
  - Duplicate submission DB queries
  - Composite fraud score calculation
  - Fraud analysis report generation
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Name similarity
# ---------------------------------------------------------------------------


def calculate_name_similarity(name1: Optional[str], name2: Optional[str]) -> float:
    """
    Calculate similarity between two name strings.

    Combines RapidFuzz plain ratio and token-sort ratio, averaged, to handle:
      - Minor spelling variations (typos, OCR errors)
      - Name component ordering differences (e.g. "John Doe" vs "Doe John")

    Args:
        name1: First name string (may be None / empty)
        name2: Second name string (may be None / empty)

    Returns:
        Float in [0.0, 1.0] where 1.0 means identical.
    """
    if not name1 or not name2:
        return 0.0

    n1 = name1.strip().lower()
    n2 = name2.strip().lower()

    try:
        from rapidfuzz import fuzz  # noqa: PLC0415

        ratio = fuzz.ratio(n1, n2) / 100.0
        token_sort = fuzz.token_sort_ratio(n1, n2) / 100.0
        return round((ratio + token_sort) / 2, 4)

    except ImportError:
        logger.warning("rapidfuzz not installed – using basic word-overlap similarity")
        s1, s2 = set(n1.split()), set(n2.split())
        if not s1 or not s2:
            return 0.0
        return round(len(s1 & s2) / max(len(s1), len(s2)), 4)


# ---------------------------------------------------------------------------
# ID format validation
# ---------------------------------------------------------------------------

_ID_PATTERNS: Dict[str, re.Pattern] = {
    "passport": re.compile(r"^[A-Z0-9]{6,9}$", re.IGNORECASE),
    "national_id": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "drivers_license": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "residence_permit": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "utility_bill": re.compile(r"^.{1,50}$"),           # Free-form reference
    "bank_statement": re.compile(r"^.{1,50}$"),
    "tax_document": re.compile(r"^[A-Z0-9\-\/]{5,20}$", re.IGNORECASE),
}


def validate_id_format(id_number: str, id_type: str) -> Tuple[bool, Optional[str]]:
    """
    Validate an ID number against the expected format for a given document type.

    Args:
        id_number: The ID / document number to validate.
        id_type:   One of the keys in _ID_PATTERNS (case-insensitive).

    Returns:
        (is_valid: bool, error_message: str | None)
    """
    if not id_number or not id_number.strip():
        return False, "ID number is empty."

    id_number = id_number.strip()
    id_type_key = id_type.strip().lower()
    pattern = _ID_PATTERNS.get(id_type_key)

    if pattern is None:
        # Unknown type – accept alphanumeric only
        if re.match(r"^[A-Z0-9\-]{1,30}$", id_number, re.IGNORECASE):
            return True, None
        return False, f"ID number '{id_number}' contains invalid characters."

    if pattern.match(id_number):
        return True, None
    return False, (
        f"ID number '{id_number}' does not match the expected format for "
        f"document type '{id_type}'."
    )


# ---------------------------------------------------------------------------
# Duplicate detection
# ---------------------------------------------------------------------------


async def check_duplicate_submission(
    db,
    name: str,
    dob: Optional[str],
    id_number: str,
) -> bool:
    """
    Asynchronously query the DB for an existing non-rejected KYC submission
    matching (applicant_name, DOB, id_number).

    Args:
        db:        AsyncSession from FastAPI dependency injection.
        name:      Full applicant name ("First Last").
        dob:       Date of birth as YYYY-MM-DD string (optional).
        id_number: Document/ID number.

    Returns:
        True if a duplicate is found.
    """
    from sqlalchemy import select, and_, func  # noqa: PLC0415
    from app.models.kyc import KYCSubmission, KYCStatus  # noqa: PLC0415

    parts = name.strip().split(maxsplit=1)
    first = parts[0].upper() if len(parts) >= 1 else ""
    last = parts[1].upper() if len(parts) >= 2 else ""

    try:
        stmt = (
            select(KYCSubmission.id)
            .where(
                and_(
                    func.upper(KYCSubmission.applicant_first_name) == first,
                    func.upper(KYCSubmission.applicant_last_name) == last,
                    KYCSubmission.primary_document_number == id_number.upper(),
                    KYCSubmission.status.notin_(
                        [KYCStatus.REJECTED, KYCStatus.CANCELLED, KYCStatus.EXPIRED]
                    ),
                )
            )
            .limit(1)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none() is not None
    except Exception as exc:
        logger.error("Duplicate check query failed", error=str(exc))
        return False


# ---------------------------------------------------------------------------
# Composite fraud score
# ---------------------------------------------------------------------------


def calculate_fraud_score(state: Dict[str, Any]) -> float:
    """
    Compute a composite fraud risk score in [0.0, 1.0].

    A higher score indicates greater fraud risk.

    Factors:
      - Each fraud flag contributes +0.15 (max 0.75 from flags)
      - Critical flags (DUPLICATE, ID_FORMAT_INVALID) contribute +0.25 each
      - Low name similarity (<0.7): +0.10
      - DOB mismatch: +0.10
      - Low OCR confidence (<0.4): +0.05
    """
    score = 0.0
    flags: List[str] = state.get("fraud_flags") or []

    critical_flags = {"DUPLICATE_SUBMISSION", "ID_FORMAT_INVALID"}

    for flag in flags:
        if flag in critical_flags:
            score += 0.25
        else:
            score += 0.15

    name_score: Optional[float] = state.get("name_match_score")
    if name_score is not None and name_score < 0.70:
        score += 0.10

    dob_match: Optional[bool] = state.get("dob_match")
    if dob_match is False:
        score += 0.10

    # Infer OCR confidence from ocr_results
    ocr_results: List[Dict[str, Any]] = state.get("ocr_results") or []
    if ocr_results:
        confs = [r.get("confidence", 0.0) for r in ocr_results]
        avg_conf = sum(confs) / len(confs)
        if avg_conf < 0.40:
            score += 0.05

    return round(min(score, 1.0), 4)


# ---------------------------------------------------------------------------
# Fraud analysis report
# ---------------------------------------------------------------------------


def generate_fraud_report(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate a structured fraud analysis report from agent state.

    Args:
        state: KYCAgentState dictionary (or compatible mapping).

    Returns:
        Dictionary suitable for storing as ai_verification_details on the
        KYCSubmission model.
    """
    fraud_score = calculate_fraud_score(state)
    flags: List[str] = state.get("fraud_flags") or []

    # Per-check results
    checks: Dict[str, Any] = {
        "name_similarity": {
            "score": state.get("name_match_score"),
            "passed": (state.get("name_match_score") or 0.0) >= 0.70,
        },
        "date_of_birth": {
            "match": state.get("dob_match"),
            "passed": state.get("dob_match") is not False,
        },
        "id_number": {
            "match": state.get("id_match"),
            "passed": state.get("id_match") is not False,
        },
        "duplicate_check": {
            "duplicate_found": state.get("duplicate_detected"),
            "passed": not state.get("duplicate_detected"),
        },
        "ocr_quality": {
            "avg_confidence": _avg_ocr_confidence(state.get("ocr_results") or []),
            "passed": _avg_ocr_confidence(state.get("ocr_results") or []) >= 0.40,
        },
    }

    risk_verdict = "CLEAR"
    if fraud_score >= 0.70:
        risk_verdict = "HIGH_RISK"
    elif fraud_score >= 0.40:
        risk_verdict = "MEDIUM_RISK"
    elif fraud_score >= 0.20:
        risk_verdict = "LOW_RISK"

    return {
        "fraud_score": fraud_score,
        "risk_verdict": risk_verdict,
        "flags": flags,
        "checks": checks,
        "overall_confidence": state.get("confidence_score"),
        "recommendation": state.get("decision"),
    }


def _avg_ocr_confidence(ocr_results: List[Dict[str, Any]]) -> float:
    if not ocr_results:
        return 0.0
    confs = [r.get("confidence", 0.0) for r in ocr_results if r.get("confidence") is not None]
    return round(sum(confs) / len(confs), 4) if confs else 0.0
