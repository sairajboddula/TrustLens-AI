"""
Government Identity Validation Agent

Simulates validation of extracted identity details against government records.

Architecture:
  - Provider abstraction: GovernmentValidationProvider interface
  - MockGovernmentValidationProvider for demo/testing
  - Real provider can be swapped in via config without changing the agent logic

Validates:
  - Full name
  - Date of birth
  - ID number

Output fields written to state:
  government_validation_status    : verified | not_verified | error
  government_match_score          : float 0.0-1.0
  government_reference_id         : str (e.g. GOV-REF-XXXXXXXX)
  government_validation_summary   : str
  government_validation_details   : dict
"""

from __future__ import annotations

import hashlib
import random
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Provider abstraction
# ---------------------------------------------------------------------------


class GovernmentValidationProvider:
    """
    Abstract interface for government identity validation.

    Concrete implementations:
      - MockGovernmentValidationProvider (demo / testing)
      - Future: real government API adapters per jurisdiction
    """

    def validate(
        self,
        full_name: str,
        date_of_birth: str,
        id_number: str,
        id_type: str,
        nationality: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Validate identity against government records.

        Returns a dict with keys:
          - reference_id (str): Government validation reference
          - name_match (bool): Name matched in records
          - dob_match (bool): DOB matched in records
          - id_match (bool): ID number matched in records
          - overall_match_score (float): Combined match score 0.0-1.0
          - status (str): verified | not_verified | error
          - message (str): Human-readable result
          - checked_at (str): ISO 8601 timestamp
        """
        raise NotImplementedError


class MockGovernmentValidationProvider(GovernmentValidationProvider):
    """
    Deterministic mock implementation for demo purposes.

    Determinism strategy:
      A SHA-256 hash of (name + dob + id_number) determines the outcome.
      - hash % 10 in [0..7] → verified (80% pass rate)
      - hash % 10 in [8..8] → partial match (10%)
      - hash % 10 in [9..9] → not_verified (10%)

    This makes outcomes stable across runs for the same input data,
    which is ideal for demo/testing.
    """

    def validate(
        self,
        full_name: str,
        date_of_birth: str,
        id_number: str,
        id_type: str,
        nationality: Optional[str] = None,
    ) -> Dict[str, Any]:
        checked_at = datetime.utcnow().isoformat() + "Z"
        ref_id = f"GOV-REF-{uuid.uuid4().hex[:8].upper()}"

        # Deterministic outcome based on input
        fingerprint = f"{full_name.lower()}:{date_of_birth}:{id_number.upper()}"
        hash_int = int(hashlib.sha256(fingerprint.encode()).hexdigest(), 16)
        bucket = hash_int % 10

        if bucket <= 7:
            # Full verification match
            name_match = True
            dob_match = True
            id_match = True
            # Score has slight variance per individual
            score = round(0.88 + (hash_int % 100) / 1000.0, 4)
            status = "verified"
            message = (
                f"Identity successfully validated against government records. "
                f"Reference: {ref_id}."
            )
        elif bucket == 8:
            # Partial match
            name_match = True
            dob_match = True
            id_match = False
            score = round(0.55 + (hash_int % 50) / 1000.0, 4)
            status = "not_verified"
            message = (
                f"Partial match: name and DOB matched but ID number could not be confirmed. "
                f"Reference: {ref_id}."
            )
        else:
            # No match
            name_match = False
            dob_match = False
            id_match = False
            score = round(0.10 + (hash_int % 30) / 1000.0, 4)
            status = "not_verified"
            message = (
                f"Identity could not be validated. No matching records found. "
                f"Reference: {ref_id}."
            )

        return {
            "reference_id": ref_id,
            "name_match": name_match,
            "dob_match": dob_match,
            "id_match": id_match,
            "overall_match_score": score,
            "status": status,
            "message": message,
            "checked_at": checked_at,
            "provider": "MockGovernmentValidationProvider v1.0",
            "jurisdiction": nationality or "INTERNATIONAL",
            "id_type_checked": id_type.upper(),
        }


# Module-level provider singleton (swap for real provider via DI / config)
_PROVIDER = MockGovernmentValidationProvider()


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def government_identity_validation_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: validate identity against government records.

    Reads:
        state["form_data"]
        state["extracted_name"], state["extracted_dob"], state["extracted_id_number"]

    Writes:
        state["government_validation_status"]
        state["government_match_score"]
        state["government_reference_id"]
        state["government_validation_summary"]
        state["government_validation_details"]
        state["current_agent"]
    """
    submission_id = state.get("kyc_submission_id", "unknown")
    logger.info("Government Identity Validation agent started", submission_id=submission_id)

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "government_identity_validation_agent"

    form_data: Dict[str, Any] = state.get("form_data") or {}

    try:
        first_name = (form_data.get("first_name") or "").strip()
        last_name = (form_data.get("last_name") or "").strip()
        full_name = f"{first_name} {last_name}".strip()
        dob = (form_data.get("date_of_birth") or "")[:10]
        id_number = (form_data.get("id_number") or "").strip()
        id_type = (form_data.get("id_type") or "unknown").strip()
        nationality = (form_data.get("nationality") or "").strip()

        if not full_name or not id_number:
            # Insufficient data to validate
            new_state.update({
                "government_validation_status": "error",
                "government_match_score": 0.0,
                "government_reference_id": None,
                "government_validation_summary": (
                    "Government validation skipped: insufficient identity data provided."
                ),
                "government_validation_details": {
                    "error": "missing_required_fields",
                    "fields": {"full_name": bool(full_name), "id_number": bool(id_number)},
                },
            })
            return new_state

        result = _PROVIDER.validate(
            full_name=full_name,
            date_of_birth=dob,
            id_number=id_number,
            id_type=id_type,
            nationality=nationality or None,
        )

        summary = result.get("message", "Validation completed.")
        details = {
            **result,
            "submitted_name": full_name,
            "submitted_dob": dob,
            "submitted_id": id_number,
        }

        new_state.update({
            "government_validation_status": result["status"],
            "government_match_score": result["overall_match_score"],
            "government_reference_id": result["reference_id"],
            "government_validation_summary": summary,
            "government_validation_details": details,
        })

        logger.info(
            "Government Identity Validation agent completed",
            submission_id=submission_id,
            status=result["status"],
            score=result["overall_match_score"],
            ref=result["reference_id"],
        )

    except Exception as exc:
        logger.error(
            "Government Identity Validation agent failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        new_state.update({
            "government_validation_status": "error",
            "government_match_score": 0.0,
            "government_reference_id": None,
            "government_validation_summary": f"Government validation failed: {exc}",
            "government_validation_details": {"error": str(exc)},
        })

    return new_state
