"""
Customer Compliance Review Agent

Simulates compliance screening for a KYC submission. Checks:
  - Missing mandatory fields
  - Unsupported nationality / country rules
  - High-risk country placeholder rule
  - Sanctions list (mock, deterministic for demo)
  - PEP (Politically Exposed Person) check (mock)

All logic is demo-safe with mock rules but realistic output structure.
Provider abstraction makes it easy to swap mocks with real APIs.

Output fields written to state:
  compliance_status    : passed | flagged | failed
  compliance_flags     : list[str]
  compliance_summary   : str
  compliance_details   : dict
  pep_result           : bool
  sanctions_result     : bool
"""

from __future__ import annotations

import hashlib
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Mock provider abstraction
# ---------------------------------------------------------------------------

# High-risk countries (ISO alpha-3 or common name substrings, demo list)
HIGH_RISK_COUNTRIES = {
    "north korea", "iran", "myanmar", "belarus",
    "prk", "irn", "mmr", "blr",
}

# Sanctioned ID number prefixes (mock – first 2 chars match)
SANCTIONED_ID_PREFIXES = {"SX", "ZZ", "XX"}

# PEP name list (mock – exact last-name match for demo)
PEP_SURNAMES = {"president", "minister", "senator", "deputy", "ambassador"}


class MockComplianceProvider:
    """
    Mock compliance provider.

    Implements deterministic rules for demo purposes.
    Real implementation would call a sanctions/PEP API here.
    """

    def check_sanctions(self, id_number: str, full_name: str) -> bool:
        """Return True if sanctioned (mock: prefix-based + name hash)."""
        prefix = (id_number or "")[:2].upper()
        if prefix in SANCTIONED_ID_PREFIXES:
            return True
        # Deterministic but low-probability hit based on name hash
        name_hash = int(hashlib.md5(full_name.lower().encode()).hexdigest(), 16)
        return (name_hash % 1000) == 0  # 0.1% of names trigger sanctions

    def check_pep(self, full_name: str) -> bool:
        """Return True if PEP (mock: word match + hash)."""
        lower = full_name.lower()
        for keyword in PEP_SURNAMES:
            if keyword in lower:
                return True
        name_hash = int(hashlib.md5(lower.encode()).hexdigest(), 16)
        return (name_hash % 2000) == 0  # 0.05% of names trigger PEP

    def is_high_risk_country(self, nationality: str) -> bool:
        """Return True if nationality is on the high-risk list."""
        if not nationality:
            return False
        lower = nationality.lower()
        return any(country in lower for country in HIGH_RISK_COUNTRIES)

    def is_supported_country(self, nationality: str) -> bool:
        """Return True if nationality is in the supported list (demo: all except a few)."""
        unsupported = {"unknown", "stateless", "n/a", "none"}
        if not nationality:
            return True  # missing is handled separately
        return nationality.lower() not in unsupported


_PROVIDER = MockComplianceProvider()


# ---------------------------------------------------------------------------
# Rules engine
# ---------------------------------------------------------------------------


def _run_compliance_rules(
    form_data: Dict[str, Any],
    provider: MockComplianceProvider,
) -> tuple[List[str], Dict[str, Any]]:
    """
    Execute all compliance rules and return (flags, details).
    """
    flags: List[str] = []
    details: Dict[str, Any] = {}

    first_name = (form_data.get("first_name") or "").strip()
    last_name = (form_data.get("last_name") or "").strip()
    full_name = f"{first_name} {last_name}".strip()
    dob = form_data.get("date_of_birth")
    id_number = (form_data.get("id_number") or "").strip()
    nationality = (form_data.get("nationality") or "").strip()
    id_type = (form_data.get("id_type") or "").strip()

    # Rule 1: Mandatory fields check
    missing = []
    if not first_name:
        missing.append("first_name")
    if not last_name:
        missing.append("last_name")
    if not dob:
        missing.append("date_of_birth")
    if not id_number:
        missing.append("id_number")
    if not id_type:
        missing.append("id_type")

    details["mandatory_fields_check"] = {
        "passed": len(missing) == 0,
        "missing_fields": missing,
    }
    if missing:
        flags.append("MISSING_MANDATORY_FIELDS")

    # Rule 2: Unsupported country check
    if nationality:
        supported = provider.is_supported_country(nationality)
        details["country_support_check"] = {
            "passed": supported,
            "nationality": nationality,
        }
        if not supported:
            flags.append("UNSUPPORTED_COUNTRY")
    else:
        details["country_support_check"] = {"passed": True, "nationality": "not_provided"}

    # Rule 3: High-risk country check
    if nationality:
        high_risk = provider.is_high_risk_country(nationality)
        details["high_risk_country_check"] = {
            "passed": not high_risk,
            "nationality": nationality,
            "is_high_risk": high_risk,
        }
        if high_risk:
            flags.append("HIGH_RISK_NATIONALITY")
    else:
        details["high_risk_country_check"] = {"passed": True, "reason": "nationality_not_provided"}

    # Rule 4: Sanctions check
    sanctions_hit = provider.check_sanctions(id_number, full_name)
    details["sanctions_check"] = {
        "passed": not sanctions_hit,
        "reference": "MOCK-SANCTIONS-LIST-v2024",
        "match_found": sanctions_hit,
    }
    if sanctions_hit:
        flags.append("SANCTIONS_MATCH_FOUND")

    # Rule 5: PEP check
    pep_hit = provider.check_pep(full_name)
    details["pep_check"] = {
        "passed": not pep_hit,
        "reference": "MOCK-PEP-DATABASE-v2024",
        "match_found": pep_hit,
    }
    if pep_hit:
        flags.append("PEP_MATCH_FOUND")

    return flags, details


# ---------------------------------------------------------------------------
# Main agent node
# ---------------------------------------------------------------------------


def customer_compliance_review_agent(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: compliance screening.

    Reads:
        state["form_data"]

    Writes:
        state["compliance_status"]
        state["compliance_flags"]
        state["compliance_summary"]
        state["compliance_details"]
        state["pep_result"]
        state["sanctions_result"]
        state["current_agent"]
    """
    submission_id = state.get("kyc_submission_id", "unknown")
    logger.info("Customer Compliance Review agent started", submission_id=submission_id)

    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]
    new_state["current_agent"] = "customer_compliance_review_agent"

    form_data: Dict[str, Any] = state.get("form_data") or {}

    try:
        flags, details = _run_compliance_rules(form_data, _PROVIDER)

        pep_result = "PEP_MATCH_FOUND" in flags
        sanctions_result = "SANCTIONS_MATCH_FOUND" in flags

        # Determine overall status
        critical_flags = {"SANCTIONS_MATCH_FOUND", "PEP_MATCH_FOUND", "HIGH_RISK_NATIONALITY"}
        if any(f in critical_flags for f in flags):
            compliance_status = "failed"
        elif flags:
            compliance_status = "flagged"
        else:
            compliance_status = "passed"

        # Build human-readable summary
        if compliance_status == "passed":
            summary = (
                "Compliance review completed. All checks passed. "
                "No sanctions, PEP, or high-risk indicators found."
            )
        elif compliance_status == "flagged":
            summary = (
                f"Compliance review completed with {len(flags)} flag(s): "
                f"{', '.join(flags)}. Manual review recommended."
            )
        else:
            summary = (
                f"Compliance review FAILED. Critical flags detected: "
                f"{', '.join(f for f in flags if f in critical_flags)}."
            )

        details["total_rules_run"] = 5
        details["flags_raised"] = len(flags)
        details["compliance_provider"] = "MockComplianceProvider v1.0"

        new_state.update({
            "compliance_status": compliance_status,
            "compliance_flags": flags,
            "compliance_summary": summary,
            "compliance_details": details,
            "pep_result": pep_result,
            "sanctions_result": sanctions_result,
        })

        logger.info(
            "Customer Compliance Review agent completed",
            submission_id=submission_id,
            status=compliance_status,
            flags=flags,
        )

    except Exception as exc:
        logger.error(
            "Customer Compliance Review agent failed",
            submission_id=submission_id,
            error=str(exc),
            exc_info=True,
        )
        new_state.update({
            "compliance_status": "failed",
            "compliance_flags": ["INTERNAL_ERROR"],
            "compliance_summary": f"Compliance review failed due to internal error: {exc}",
            "compliance_details": {"error": str(exc)},
        })

    return new_state
