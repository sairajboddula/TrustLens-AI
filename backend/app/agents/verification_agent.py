"""
KYC Verification Agent

Compares submitted form data against OCR-extracted document data and
computes per-field confidence scores.  Responsibilities:
  - Fuzzy name matching via RapidFuzz
  - Exact / normalised DOB comparison
  - ID number format validation and match check
  - Duplicate-submission detection (queries DB)
  - Fraud-flag generation
  - Overall confidence score calculation
"""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------

NAME_SIMILARITY_THRESHOLD = 0.70   # min score to consider names matching
DOB_FORMAT = "%Y-%m-%d"

ID_PATTERNS: Dict[str, re.Pattern] = {
    "PASSPORT": re.compile(r"^[A-Z0-9]{6,9}$", re.IGNORECASE),
    "NATIONAL_ID": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "DRIVERS_LICENSE": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "RESIDENCE_PERMIT": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fuzzy_name_similarity(name1: Optional[str], name2: Optional[str]) -> float:
    """
    Return a similarity score in [0.0, 1.0] using RapidFuzz.

    Averages the plain ratio and the token-sort ratio to handle name
    component ordering differences.
    """
    if not name1 or not name2:
        return 0.0
    try:
        from rapidfuzz import fuzz  # noqa: PLC0415

        ratio = fuzz.ratio(name1.lower(), name2.lower()) / 100.0
        token_sort = fuzz.token_sort_ratio(name1.lower(), name2.lower()) / 100.0
        return round((ratio + token_sort) / 2, 4)
    except ImportError:
        # Fallback: simple character-level overlap
        s1, s2 = set(name1.lower().split()), set(name2.lower().split())
        if not s1 or not s2:
            return 0.0
        return round(len(s1 & s2) / max(len(s1), len(s2)), 4)


def _normalize_dob(dob_str: Optional[str]) -> Optional[datetime]:
    """Parse YYYY-MM-DD string into a date; return None on failure."""
    if not dob_str:
        return None
    try:
        return datetime.strptime(dob_str.strip(), DOB_FORMAT)
    except ValueError:
        return None


def _validate_id_format(id_number: str, id_type: str) -> bool:
    """Return True if *id_number* matches the expected format for *id_type*."""
    pattern = ID_PATTERNS.get(id_type.upper())
    if pattern is None:
        # Unknown type – accept non-empty alphanumeric
        return bool(re.match(r"^[A-Z0-9\-]{1,30}$", id_number, re.IGNORECASE))
    return bool(pattern.match(id_number))


def _check_duplicate(
    submission_id: str,
    form_data: Dict[str, Any],
) -> bool:
    """
    Query the DB for existing approved/processing submissions with the same
    applicant name + DOB + ID number combination.

    Returns True if a duplicate is found.
    """
    import asyncio  # noqa: PLC0415

    from sqlalchemy import select, and_  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.kyc import KYCSubmission, KYCStatus  # noqa: PLC0415

    first_name = form_data.get("first_name", "").strip().upper()
    last_name = form_data.get("last_name", "").strip().upper()
    dob = form_data.get("date_of_birth")
    id_number = form_data.get("id_number", "").strip().upper()

    duplicate_found = False

    async def _query():
        nonlocal duplicate_found
        async with AsyncSessionLocal() as session:
            stmt = (
                select(KYCSubmission.id)
                .where(
                    and_(
                        KYCSubmission.applicant_first_name.ilike(first_name),
                        KYCSubmission.applicant_last_name.ilike(last_name),
                        KYCSubmission.primary_document_number == id_number,
                        KYCSubmission.id != submission_id,
                        KYCSubmission.status.in_(
                            [
                                KYCStatus.APPROVED,
                                KYCStatus.PROCESSING,
                                KYCStatus.SUBMITTED,
                                KYCStatus.UNDER_REVIEW,
                            ]
                        ),
                    )
                )
                .limit(1)
            )
            result = await session.execute(stmt)
            duplicate_found = result.scalar_one_or_none() is not None

    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _query())
                future.result(timeout=10)
        except RuntimeError:
            asyncio.run(_query())
    except Exception as exc:
        logger.warning("Duplicate check DB query failed", error=str(exc))
        # On failure, do not falsely flag duplicate
        duplicate_found = False

    return duplicate_found


# ---------------------------------------------------------------------------
# Confidence scoring
# ---------------------------------------------------------------------------


def _compute_confidence_score(
    name_score: float,
    dob_match: bool,
    id_match: bool,
    id_format_valid: bool,
    avg_ocr_confidence: float,
    fraud_flags: List[str],
) -> float:
    """
    Compute a weighted overall confidence score in [0.0, 1.0].

    Weights:
        name similarity     : 30%
        DOB match           : 25%
        ID number match     : 25%
        OCR confidence      : 20%
    Fraud flags apply a flat penalty per flag (max deduction: 40%).
    """
    name_weight = 0.30
    dob_weight = 0.25
    id_weight = 0.25
    ocr_weight = 0.20

    score = (
        name_score * name_weight
        + (1.0 if dob_match else 0.0) * dob_weight
        + (1.0 if id_match and id_format_valid else 0.0) * id_weight
        + avg_ocr_confidence * ocr_weight
    )

    # Penalty per fraud flag: 0.08 each, max total 0.40
    penalty = min(len(fraud_flags) * 0.08, 0.40)
    score = max(0.0, score - penalty)

    return round(score, 4)


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def verification_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: compare form data vs OCR data and compute scores.

    Reads:
        state["form_data"]
        state["extracted_name"], state["extracted_dob"],
        state["extracted_id_number"], state["ocr_results"]

    Writes:
        state["name_match_score"]
        state["dob_match"]
        state["id_match"]
        state["fraud_flags"]
        state["duplicate_detected"]
        state["confidence_score"]
        state["current_agent"]
        state["errors"]
    """
    logger.info(
        "Verification agent started",
        submission_id=state.get("kyc_submission_id"),
    )

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "verification_agent"

    form_data: Dict[str, Any] = state.get("form_data") or {}
    errors: List[str] = list(state.get("errors") or [])
    fraud_flags: List[str] = []

    # -----------------------------------------------------------------------
    # 1. Name comparison
    # -----------------------------------------------------------------------
    form_first = form_data.get("first_name", "")
    form_last = form_data.get("last_name", "")
    form_full_name = f"{form_first} {form_last}".strip()
    extracted_name: Optional[str] = state.get("extracted_name")

    name_score = _fuzzy_name_similarity(form_full_name, extracted_name)
    name_match = name_score >= NAME_SIMILARITY_THRESHOLD

    if not name_match:
        fraud_flags.append("NAME_MISMATCH")
        logger.warning(
            "Name mismatch",
            submission_id=state.get("kyc_submission_id"),
            form_name=form_full_name,
            extracted_name=extracted_name,
            score=name_score,
        )

    # -----------------------------------------------------------------------
    # 2. DOB comparison
    # -----------------------------------------------------------------------
    form_dob = _normalize_dob(form_data.get("date_of_birth"))
    extracted_dob = _normalize_dob(state.get("extracted_dob"))

    if form_dob and extracted_dob:
        dob_match = form_dob.date() == extracted_dob.date()
    elif form_dob is None and extracted_dob is None:
        dob_match = True  # both absent – not a mismatch
    else:
        dob_match = False

    if not dob_match:
        fraud_flags.append("DOB_MISMATCH")
        logger.warning(
            "DOB mismatch",
            submission_id=state.get("kyc_submission_id"),
            form_dob=str(form_dob),
            extracted_dob=str(extracted_dob),
        )

    # -----------------------------------------------------------------------
    # 3. ID number comparison
    # -----------------------------------------------------------------------
    form_id = (form_data.get("id_number") or "").strip().upper()
    extracted_id = (state.get("extracted_id_number") or "").strip().upper()
    id_type = (form_data.get("id_type") or "").strip().upper()

    id_format_valid = _validate_id_format(form_id, id_type) if form_id else False
    if not id_format_valid:
        fraud_flags.append("ID_FORMAT_INVALID")

    id_match = bool(form_id and extracted_id and form_id == extracted_id)
    if not id_match and extracted_id:
        fraud_flags.append("ID_MISMATCH")

    # -----------------------------------------------------------------------
    # 4. OCR confidence check
    # -----------------------------------------------------------------------
    ocr_results: List[Dict[str, Any]] = state.get("ocr_results") or []
    ocr_confidences = [
        r["confidence"] for r in ocr_results if r.get("confidence") is not None
    ]
    avg_ocr_conf = (
        round(sum(ocr_confidences) / len(ocr_confidences), 4) if ocr_confidences else 0.0
    )
    if avg_ocr_conf < 0.40:
        fraud_flags.append("LOW_OCR_CONFIDENCE")

    # -----------------------------------------------------------------------
    # 5. Duplicate detection
    # -----------------------------------------------------------------------
    duplicate_detected = _check_duplicate(
        state.get("kyc_submission_id", ""), form_data
    )
    if duplicate_detected:
        fraud_flags.append("DUPLICATE_SUBMISSION")
        logger.warning(
            "Duplicate submission detected",
            submission_id=state.get("kyc_submission_id"),
        )

    # -----------------------------------------------------------------------
    # 6. Compute overall confidence score
    # -----------------------------------------------------------------------
    confidence_score = _compute_confidence_score(
        name_score=name_score,
        dob_match=dob_match,
        id_match=id_match,
        id_format_valid=id_format_valid,
        avg_ocr_confidence=avg_ocr_conf,
        fraud_flags=fraud_flags,
    )

    # -----------------------------------------------------------------------
    # 7. Write back
    # -----------------------------------------------------------------------
    new_state["name_match_score"] = name_score
    new_state["dob_match"] = dob_match
    new_state["id_match"] = id_match
    new_state["fraud_flags"] = fraud_flags
    new_state["duplicate_detected"] = duplicate_detected
    new_state["confidence_score"] = confidence_score
    new_state["errors"] = errors

    logger.info(
        "Verification agent completed",
        submission_id=state.get("kyc_submission_id"),
        confidence_score=confidence_score,
        fraud_flags=fraud_flags,
        name_score=name_score,
        dob_match=dob_match,
        id_match=id_match,
        duplicate=duplicate_detected,
    )

    return new_state
