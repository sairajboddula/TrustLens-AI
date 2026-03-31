"""
Tests for LangGraph Agent Nodes

Covers:
  - ingestion_agent: field validation and sanitisation
  - document_processing_agent: OCR mock integration
  - verification_agent: name/DOB/ID matching and fraud flags
  - decision_agent: APPROVED / REJECTED / MANUAL_REVIEW thresholds
  - Full end-to-end graph execution with all mocks in place
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.state import KYCAgentState
from app.agents.ingestion_agent import (
    ingestion_agent,
    _validate_required_fields,
    _validate_dob,
    _validate_id_number,
    _sanitize_form_data,
)
from app.agents.verification_agent import (
    verification_agent,
    _fuzzy_name_similarity,
    _validate_id_format,
)
from app.agents.decision_agent import (
    decision_agent,
    _classify_risk,
    APPROVE_THRESHOLD,
    REJECT_THRESHOLD,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides) -> KYCAgentState:
    """Construct a minimal valid KYCAgentState for testing."""
    today = datetime.now(timezone.utc)
    dob = (today - timedelta(days=365 * 30)).strftime("%Y-%m-%d")

    state: KYCAgentState = {
        "kyc_submission_id": str(uuid.uuid4()),
        "user_id": str(uuid.uuid4()),
        "form_data": {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": dob,
            "id_type": "passport",
            "id_number": "AB123456",
            "email": "john.doe@example.com",
            "phone": "+15555550100",
            "address": "123 Main St",
            "nationality": "USA",
        },
        "document_ids": [str(uuid.uuid4())],
        "current_agent": "",
        "retry_count": 0,
        "errors": [],
        "ocr_results": [],
        "extracted_name": None,
        "extracted_dob": None,
        "extracted_id_number": None,
        "extracted_address": None,
        "name_match_score": None,
        "dob_match": None,
        "id_match": None,
        "fraud_flags": [],
        "duplicate_detected": None,
        "confidence_score": None,
        "risk_level": None,
        "decision": None,
        "decision_reason": None,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "completed_at": None,
        "processing_time_ms": None,
    }
    state.update(overrides)  # type: ignore[arg-type]
    return state


# ---------------------------------------------------------------------------
# Ingestion agent tests
# ---------------------------------------------------------------------------


def test_ingestion_agent_validates_fields():
    """Ingestion agent succeeds for a fully valid state."""
    state = _base_state()
    result = ingestion_agent(state)
    assert result["current_agent"] == "ingestion_agent"
    assert result["errors"] == []
    # Name fields should be title-cased
    assert result["form_data"]["first_name"] == "John"
    assert result["form_data"]["last_name"] == "Doe"


def test_ingestion_agent_rejects_missing_fields():
    """Ingestion agent adds errors for each missing required field."""
    state = _base_state(form_data={})
    result = ingestion_agent(state)
    assert len(result["errors"]) > 0
    error_text = " ".join(result["errors"])
    for field in ("first_name", "last_name", "date_of_birth", "id_number", "id_type"):
        assert field in error_text


def test_ingestion_agent_rejects_invalid_dob():
    """Ingestion agent rejects a date-of-birth that is not YYYY-MM-DD."""
    state = _base_state()
    state["form_data"]["date_of_birth"] = "15/01/1990"  # wrong format
    result = ingestion_agent(state)
    assert any("date_of_birth" in e or "format" in e.lower() for e in result["errors"])


def test_ingestion_agent_rejects_future_dob():
    """Ingestion agent rejects a future date-of-birth."""
    future = (datetime.now(timezone.utc) + timedelta(days=10)).strftime("%Y-%m-%d")
    state = _base_state()
    state["form_data"]["date_of_birth"] = future
    result = ingestion_agent(state)
    assert any("past" in e.lower() or "future" in e.lower() or "date_of_birth" in e for e in result["errors"])


def test_ingestion_agent_sanitizes_input():
    """Ingestion agent strips whitespace and title-cases names."""
    state = _base_state()
    state["form_data"]["first_name"] = "  JOHN  "
    state["form_data"]["last_name"] = "  doe  "
    result = ingestion_agent(state)
    assert result["form_data"]["first_name"] == "John"
    assert result["form_data"]["last_name"] == "Doe"


def test_ingestion_agent_uppercase_id():
    """ID number and type are uppercased after sanitisation."""
    state = _base_state()
    state["form_data"]["id_number"] = "ab123456"
    state["form_data"]["id_type"] = "passport"
    result = ingestion_agent(state)
    assert result["form_data"]["id_number"] == "AB123456"
    assert result["form_data"]["id_type"] == "PASSPORT"


# ---------------------------------------------------------------------------
# Document processing agent tests
# ---------------------------------------------------------------------------


def test_document_agent_with_mock_ocr():
    """Document processing agent extracts name/DOB/ID from mocked OCR output."""
    fake_ocr_text = "JOHN DOE\nDOB: 1990-01-15\nID: AB123456"

    with patch(
        "app.agents.document_processing_agent.perform_ocr",
        return_value={
            "raw_text": fake_ocr_text,
            "confidence": 0.92,
            "processing_time_ms": 120,
            "error": None,
        },
    ):
        from app.agents.document_processing_agent import document_processing_agent

        state = _base_state()
        result = document_processing_agent(state)

    assert result["current_agent"] == "document_processing_agent"
    # OCR results should be populated
    assert len(result["ocr_results"]) > 0 or result.get("extracted_name") is not None


def test_document_agent_handles_ocr_error():
    """Document processing agent gracefully handles OCR failure."""
    with patch(
        "app.agents.document_processing_agent.perform_ocr",
        return_value={
            "raw_text": "",
            "confidence": 0.0,
            "processing_time_ms": 50,
            "error": "OCR engine unavailable",
        },
    ):
        from app.agents.document_processing_agent import document_processing_agent

        state = _base_state()
        result = document_processing_agent(state)

    # Errors should be recorded but agent should not crash
    assert result["current_agent"] == "document_processing_agent"


# ---------------------------------------------------------------------------
# Verification agent tests
# ---------------------------------------------------------------------------


def test_verification_agent_name_match():
    """Verification agent computes high name match score for identical names."""
    state = _base_state(
        extracted_name="John Doe",
        extracted_dob="1990-01-15",
        extracted_id_number="AB123456",
        ocr_results=[{"document_id": "doc1", "confidence": 0.95, "raw_text": "...", "processing_time_ms": 100, "error": None}],
    )
    state["form_data"]["date_of_birth"] = "1990-01-15"

    with patch("app.agents.verification_agent._check_duplicate", return_value=False):
        result = verification_agent(state)

    assert result["name_match_score"] is not None
    assert result["name_match_score"] >= 0.85
    assert "NAME_MISMATCH" not in result["fraud_flags"]


def test_verification_agent_fraud_detection():
    """Verification agent flags NAME_MISMATCH when names differ significantly."""
    state = _base_state(
        extracted_name="Jane Smith",  # completely different name
        extracted_dob="1990-01-15",
        extracted_id_number="AB123456",
        ocr_results=[{"document_id": "doc1", "confidence": 0.90, "raw_text": "...", "processing_time_ms": 100, "error": None}],
    )
    state["form_data"]["date_of_birth"] = "1990-01-15"

    with patch("app.agents.verification_agent._check_duplicate", return_value=False):
        result = verification_agent(state)

    assert "NAME_MISMATCH" in result["fraud_flags"]
    assert result["name_match_score"] < 0.70


def test_verification_agent_dob_mismatch_flag():
    """DOB mismatch generates DOB_MISMATCH fraud flag."""
    state = _base_state(
        extracted_name="John Doe",
        extracted_dob="1985-06-20",  # different from form data
        extracted_id_number="AB123456",
        ocr_results=[{"document_id": "doc1", "confidence": 0.90, "raw_text": "...", "processing_time_ms": 100, "error": None}],
    )
    state["form_data"]["date_of_birth"] = "1990-01-15"

    with patch("app.agents.verification_agent._check_duplicate", return_value=False):
        result = verification_agent(state)

    assert "DOB_MISMATCH" in result["fraud_flags"]
    assert result["dob_match"] is False


def test_verification_agent_duplicate_detection():
    """Verification agent sets DUPLICATE_SUBMISSION flag when duplicate found."""
    state = _base_state(
        extracted_name="John Doe",
        extracted_dob="1990-01-15",
        extracted_id_number="AB123456",
        ocr_results=[{"document_id": "doc1", "confidence": 0.90, "raw_text": "...", "processing_time_ms": 100, "error": None}],
    )
    state["form_data"]["date_of_birth"] = "1990-01-15"

    with patch("app.agents.verification_agent._check_duplicate", return_value=True):
        result = verification_agent(state)

    assert result["duplicate_detected"] is True
    assert "DUPLICATE_SUBMISSION" in result["fraud_flags"]


# ---------------------------------------------------------------------------
# Decision agent tests
# ---------------------------------------------------------------------------


def test_decision_agent_approves_high_score():
    """Decision agent returns APPROVED for high confidence score with no flags."""
    state = _base_state(
        confidence_score=0.95,
        fraud_flags=[],
        name_match_score=0.98,
        dob_match=True,
        id_match=True,
    )
    with patch("app.agents.decision_agent._update_db"):
        result = decision_agent(state)

    assert result["decision"] == "APPROVED"
    assert result["risk_level"] == "LOW"
    assert result["decision_reason"] is not None


def test_decision_agent_rejects_low_score():
    """Decision agent returns REJECTED for confidence score below threshold."""
    state = _base_state(
        confidence_score=0.25,  # below REJECT_THRESHOLD (0.50)
        fraud_flags=["NAME_MISMATCH", "DOB_MISMATCH"],
        name_match_score=0.40,
        dob_match=False,
        id_match=False,
    )
    with patch("app.agents.decision_agent._update_db"):
        result = decision_agent(state)

    assert result["decision"] == "REJECTED"
    assert result["risk_level"] in ("HIGH", "CRITICAL")


def test_decision_agent_manual_review_medium_score():
    """Decision agent returns MANUAL_REVIEW for confidence in the middle band."""
    state = _base_state(
        confidence_score=0.62,  # between REJECT (0.50) and APPROVE (0.85)
        fraud_flags=["NAME_MISMATCH"],
        name_match_score=0.65,
        dob_match=True,
        id_match=True,
    )
    with patch("app.agents.decision_agent._update_db"):
        result = decision_agent(state)

    assert result["decision"] == "MANUAL_REVIEW"


def test_decision_agent_critical_flag_causes_rejection():
    """DUPLICATE_SUBMISSION critical flag forces REJECTED even with decent score."""
    state = _base_state(
        confidence_score=0.70,
        fraud_flags=["DUPLICATE_SUBMISSION"],
        name_match_score=0.90,
        dob_match=True,
        id_match=True,
    )
    with patch("app.agents.decision_agent._update_db"):
        result = decision_agent(state)

    assert result["decision"] == "REJECTED"


def test_decision_agent_sets_timestamps():
    """Decision agent sets completed_at and processing_time_ms."""
    state = _base_state(
        confidence_score=0.90,
        fraud_flags=[],
    )
    with patch("app.agents.decision_agent._update_db"):
        result = decision_agent(state)

    assert result["completed_at"] is not None
    assert result["processing_time_ms"] is not None
    assert result["processing_time_ms"] >= 0


# ---------------------------------------------------------------------------
# Full graph end-to-end test
# ---------------------------------------------------------------------------


def test_full_graph_end_to_end():
    """
    Run the complete KYC LangGraph pipeline with all external I/O mocked.
    Validates the graph reaches a terminal decision node.
    """
    fake_ocr_text = "JOHN DOE\n1990-01-15\nAB123456"

    mock_perform_ocr = MagicMock(
        return_value={
            "raw_text": fake_ocr_text,
            "confidence": 0.90,
            "processing_time_ms": 80,
            "error": None,
        }
    )

    initial_state = _base_state()

    with (
        patch("app.agents.document_processing_agent.perform_ocr", mock_perform_ocr),
        patch("app.agents.verification_agent._check_duplicate", return_value=False),
        patch("app.agents.decision_agent._update_db"),
    ):
        from app.graph.kyc_graph import get_kyc_graph

        graph = get_kyc_graph()
        final_state = graph.invoke(initial_state)

    # Graph must finish and produce a decision
    assert final_state["decision"] in ("APPROVED", "REJECTED", "MANUAL_REVIEW")
    assert final_state["completed_at"] is not None
    assert final_state["current_agent"] == "decision_agent"
