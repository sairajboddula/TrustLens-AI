"""
KYC Ingestion Agent

Validates and sanitizes all incoming KYC form data before the pipeline
proceeds to document processing.  Responsible for:
  - Ensuring all required fields are present and non-empty
  - Stripping whitespace and normalising string case
  - Validating date formats (DOB must be YYYY-MM-DD)
  - Validating ID-number format with per-type regex rules
  - Persisting the sanitised form_data back onto the agent state
  - Logging the ingestion event
"""

from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Dict, List

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Field requirement definitions
# ---------------------------------------------------------------------------

REQUIRED_FIELDS: List[str] = [
    "first_name",
    "last_name",
    "date_of_birth",
    "id_number",
    "id_type",
]

# ---------------------------------------------------------------------------
# ID-type regex validators
# ---------------------------------------------------------------------------

ID_PATTERNS: Dict[str, re.Pattern] = {
    "passport": re.compile(r"^[A-Z0-9]{6,9}$", re.IGNORECASE),
    "national_id": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "drivers_license": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
    "residence_permit": re.compile(r"^[A-Z0-9\-]{5,20}$", re.IGNORECASE),
}

# Date format accepted for date-of-birth
DOB_FORMAT = "%Y-%m-%d"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _strip_normalize(value: Any) -> str:
    """Strip whitespace and NFC-normalize a string value."""
    if not isinstance(value, str):
        value = str(value)
    return unicodedata.normalize("NFC", value.strip())


def _validate_required_fields(form_data: Dict[str, Any]) -> List[str]:
    """Return a list of error messages for missing/blank required fields."""
    errors: List[str] = []
    for field in REQUIRED_FIELDS:
        val = form_data.get(field)
        if val is None or (isinstance(val, str) and not val.strip()):
            errors.append(f"Required field '{field}' is missing or empty.")
    return errors


def _validate_dob(dob_str: str) -> List[str]:
    """Validate that *dob_str* is a valid YYYY-MM-DD date in the past."""
    errors: List[str] = []
    try:
        dob = datetime.strptime(dob_str, DOB_FORMAT).date()
    except ValueError:
        errors.append(
            f"Invalid date_of_birth format '{dob_str}'. Expected YYYY-MM-DD."
        )
        return errors

    today = datetime.now(timezone.utc).date()
    if dob >= today:
        errors.append("date_of_birth must be in the past.")
    if (today - dob).days > 365 * 120:
        errors.append("date_of_birth implies age > 120 years – likely invalid.")
    return errors


def _validate_id_number(id_number: str, id_type: str) -> List[str]:
    """Validate ID number format against the known pattern for *id_type*."""
    errors: List[str] = []
    id_type_lower = id_type.lower()
    pattern = ID_PATTERNS.get(id_type_lower)
    if pattern is None:
        # Unknown id_type – accept any non-empty alphanumeric string
        if not re.match(r"^[A-Z0-9\-]{1,30}$", id_number, re.IGNORECASE):
            errors.append(
                f"id_number '{id_number}' contains invalid characters."
            )
    elif not pattern.match(id_number):
        errors.append(
            f"id_number '{id_number}' does not match the expected format for "
            f"id_type '{id_type}'."
        )
    return errors


def _sanitize_form_data(form_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a sanitised copy of *form_data*.

    String fields are stripped and NFC-normalised.
    Name fields are title-cased.
    id_number and id_type are upper-cased.
    date_of_birth is kept as-is (already validated).
    """
    sanitized: Dict[str, Any] = {}

    for key, value in form_data.items():
        if isinstance(value, str):
            clean = _strip_normalize(value)
            if key in ("first_name", "last_name"):
                clean = clean.title()
            elif key in ("id_number", "id_type"):
                clean = clean.upper()
            elif key == "email":
                clean = clean.lower()
            sanitized[key] = clean
        else:
            sanitized[key] = value

    return sanitized


# ---------------------------------------------------------------------------
# Agent node
# ---------------------------------------------------------------------------


def ingestion_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: validate and sanitise the incoming KYC form data.

    Reads:
        state["form_data"]
        state["document_ids"]
        state["kyc_submission_id"]

    Writes:
        state["form_data"]        – sanitised copy
        state["current_agent"]    – "ingestion_agent"
        state["errors"]           – appends validation errors if any
    """
    logger.info(
        "Ingestion agent started",
        submission_id=state.get("kyc_submission_id"),
        user_id=state.get("user_id"),
    )

    # Work on a mutable copy
    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "ingestion_agent"

    form_data: Dict[str, Any] = state.get("form_data") or {}
    errors: List[str] = list(state.get("errors") or [])

    # --- 1. Required-field validation ----------------------------------------
    field_errors = _validate_required_fields(form_data)
    errors.extend(field_errors)

    if field_errors:
        logger.warning(
            "Ingestion: required field validation failed",
            submission_id=state.get("kyc_submission_id"),
            missing=field_errors,
        )
        new_state["errors"] = errors
        return new_state

    # --- 2. Sanitise inputs ---------------------------------------------------
    sanitized = _sanitize_form_data(form_data)

    # --- 3. Validate DOB ------------------------------------------------------
    dob_errors = _validate_dob(sanitized.get("date_of_birth", ""))
    errors.extend(dob_errors)

    # --- 4. Validate ID number ------------------------------------------------
    id_errors = _validate_id_number(
        sanitized.get("id_number", ""),
        sanitized.get("id_type", ""),
    )
    errors.extend(id_errors)

    # --- 5. Validate document_ids list ----------------------------------------
    doc_ids: List[str] = state.get("document_ids") or []
    if not doc_ids:
        # Log a warning but do NOT add to errors — the document processing and
        # admin-review agents tolerate missing documents and produce degraded
        # (but valid) output.  Adding an error here would route the pipeline
        # to the error handler and skip all admin-review steps.
        logger.warning(
            "Ingestion: no document_ids provided — admin agents will run without OCR data",
            submission_id=state.get("kyc_submission_id"),
        )

    # --- 6. Persist results ---------------------------------------------------
    new_state["form_data"] = sanitized
    new_state["errors"] = errors

    if errors:
        logger.warning(
            "Ingestion agent completed with validation errors",
            submission_id=state.get("kyc_submission_id"),
            error_count=len(errors),
            errors=errors,
        )
    else:
        logger.info(
            "Ingestion agent completed successfully",
            submission_id=state.get("kyc_submission_id"),
            id_type=sanitized.get("id_type"),
        )

    return new_state
