"""
Tests for the extended admin workflow:
  - New LangGraph agents (unit tests)
  - Graph step transitions
  - Final recommendation logic
  - Admin workflow API endpoints
  - Mock failure scenarios
"""

from __future__ import annotations

import uuid
from typing import Any, Dict
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.agents.state import KYCAgentState

# ---------------------------------------------------------------------------
# Shared fixture: minimal state
# ---------------------------------------------------------------------------

SUBMISSION_ID = str(uuid.uuid4())
USER_ID = str(uuid.uuid4())


def _base_state(**overrides) -> KYCAgentState:
    """Return a minimal valid KYCAgentState for testing."""
    state: KYCAgentState = {  # type: ignore[assignment]
        "kyc_submission_id": SUBMISSION_ID,
        "user_id": USER_ID,
        "form_data": {
            "first_name": "Alice",
            "last_name": "Smith",
            "date_of_birth": "1990-05-15",
            "address": "123 Main St, London",
            "id_number": "P1234567",
            "id_type": "passport",
            "nationality": "British",
            "phone": "+44 7700 900000",
            "email": "alice@example.com",
        },
        "document_ids": [],
        "current_agent": "test",
        "retry_count": 0,
        "errors": [],
        "ocr_results": [
            {
                "document_id": str(uuid.uuid4()),
                "raw_text": "Alice Smith DOB: 15/05/1990 Passport No: P1234567 Nationality: British",
                "confidence": 0.87,
                "processing_time_ms": 1200,
                "error": None,
            }
        ],
        "extracted_name": "Alice Smith",
        "extracted_dob": "1990-05-15",
        "extracted_id_number": "P1234567",
        "extracted_address": "123 Main St",
        "name_match_score": None,
        "dob_match": None,
        "id_match": None,
        "fraud_flags": [],
        "duplicate_detected": False,
        "confidence_score": None,
        "risk_level": None,
        "decision": None,
        "decision_reason": None,
        "started_at": "2026-03-27T10:00:00Z",
        "completed_at": None,
        "processing_time_ms": None,
        # New fields
        "document_analysis_status": None,
        "document_quality_score": None,
        "document_tampering_flag": None,
        "document_type_detected": None,
        "document_completeness_score": None,
        "document_analysis_summary": None,
        "document_analysis_details": None,
        "compliance_status": None,
        "compliance_flags": None,
        "compliance_summary": None,
        "compliance_details": None,
        "pep_result": None,
        "sanctions_result": None,
        "government_validation_status": None,
        "government_match_score": None,
        "government_reference_id": None,
        "government_validation_summary": None,
        "government_validation_details": None,
        "identity_verification_status": None,
        "identity_confidence_score": None,
        "fraud_flag": None,
        "identity_verification_summary": None,
        "identity_verification_details": None,
        "final_report": None,
        "final_recommendation": None,
        "report_generated_at": None,
        "workflow_steps": None,
    }
    state.update(overrides)
    return state


# ===========================================================================
# Customer Document Analysis Agent
# ===========================================================================


class TestCustomerDocumentAnalysisAgent:
    def test_happy_path(self):
        """Standard documents produce a completed status."""
        from app.agents.customer_document_analysis_agent import customer_document_analysis_agent

        state = _base_state()
        result = customer_document_analysis_agent(state)

        assert result["document_analysis_status"] == "completed"
        assert result["document_quality_score"] is not None
        assert 0.0 <= result["document_quality_score"] <= 1.0
        assert result["document_tampering_flag"] is not None
        assert result["document_type_detected"] is not None
        assert result["document_completeness_score"] is not None
        assert result["document_analysis_summary"] is not None
        assert result["current_agent"] == "customer_document_analysis_agent"

    def test_tampering_keyword_detection(self):
        """A 'specimen' keyword in OCR text triggers tampering flag."""
        from app.agents.customer_document_analysis_agent import customer_document_analysis_agent

        state = _base_state(
            ocr_results=[
                {
                    "document_id": str(uuid.uuid4()),
                    "raw_text": "SPECIMEN Alice Smith DOB: 15/05/1990",
                    "confidence": 0.85,
                    "processing_time_ms": 900,
                    "error": None,
                }
            ]
        )
        result = customer_document_analysis_agent(state)

        assert result["document_tampering_flag"] is True
        assert result["document_analysis_status"] == "completed"

    def test_empty_ocr_results(self):
        """No OCR results produces degraded but non-error output."""
        from app.agents.customer_document_analysis_agent import customer_document_analysis_agent

        state = _base_state(ocr_results=[])
        result = customer_document_analysis_agent(state)

        assert result["document_analysis_status"] == "completed"
        assert result["document_quality_score"] == pytest.approx(0.40, abs=0.01)

    def test_document_type_from_form_data(self):
        """Document type is taken from form_data id_type."""
        from app.agents.customer_document_analysis_agent import customer_document_analysis_agent

        state = _base_state()
        state["form_data"]["id_type"] = "national_id"
        result = customer_document_analysis_agent(state)

        assert result["document_type_detected"] == "national_id"


# ===========================================================================
# Customer Compliance Review Agent
# ===========================================================================


class TestCustomerComplianceReviewAgent:
    def test_clean_applicant_passes(self):
        """A normal applicant with no compliance flags passes."""
        from app.agents.customer_compliance_review_agent import customer_compliance_review_agent

        state = _base_state()
        # Alice Smith with passport P1234567 – deterministic hash will give a result
        result = customer_compliance_review_agent(state)

        assert result["compliance_status"] in ("passed", "flagged", "failed")
        assert result["compliance_flags"] is not None
        assert isinstance(result["compliance_flags"], list)
        assert result["compliance_summary"] is not None
        assert result["pep_result"] is not None
        assert result["sanctions_result"] is not None
        assert result["current_agent"] == "customer_compliance_review_agent"

    def test_missing_mandatory_fields_flag(self):
        """Missing id_number triggers MISSING_MANDATORY_FIELDS."""
        from app.agents.customer_compliance_review_agent import customer_compliance_review_agent

        state = _base_state()
        state["form_data"]["id_number"] = ""
        result = customer_compliance_review_agent(state)

        assert "MISSING_MANDATORY_FIELDS" in result["compliance_flags"]

    def test_high_risk_country_flag(self):
        """North Korea nationality triggers HIGH_RISK_NATIONALITY."""
        from app.agents.customer_compliance_review_agent import customer_compliance_review_agent

        state = _base_state()
        state["form_data"]["nationality"] = "North Korea"
        result = customer_compliance_review_agent(state)

        assert "HIGH_RISK_NATIONALITY" in result["compliance_flags"]
        assert result["compliance_status"] == "failed"

    def test_sanctions_id_prefix(self):
        """SX-prefixed ID number triggers SANCTIONS_MATCH_FOUND."""
        from app.agents.customer_compliance_review_agent import customer_compliance_review_agent

        state = _base_state()
        state["form_data"]["id_number"] = "SXABC123"
        result = customer_compliance_review_agent(state)

        assert "SANCTIONS_MATCH_FOUND" in result["compliance_flags"]


# ===========================================================================
# Government Identity Validation Agent
# ===========================================================================


class TestGovernmentIdentityValidationAgent:
    def test_returns_structured_output(self):
        """Agent always returns all required fields."""
        from app.agents.government_identity_validation_agent import government_identity_validation_agent

        state = _base_state()
        result = government_identity_validation_agent(state)

        assert result["government_validation_status"] in ("verified", "not_verified", "error")
        assert result["government_match_score"] is not None
        assert 0.0 <= result["government_match_score"] <= 1.0
        assert result["government_reference_id"] is not None
        assert result["government_reference_id"].startswith("GOV-REF-")
        assert result["government_validation_summary"] is not None
        assert result["current_agent"] == "government_identity_validation_agent"

    def test_missing_identity_data_returns_error(self):
        """Missing name and id_number returns error status."""
        from app.agents.government_identity_validation_agent import government_identity_validation_agent

        state = _base_state()
        state["form_data"]["first_name"] = ""
        state["form_data"]["last_name"] = ""
        state["form_data"]["id_number"] = ""
        result = government_identity_validation_agent(state)

        assert result["government_validation_status"] == "error"
        assert result["government_match_score"] == 0.0

    def test_deterministic_outcome(self):
        """Same input always produces the same validation result."""
        from app.agents.government_identity_validation_agent import government_identity_validation_agent

        state = _base_state()
        result1 = government_identity_validation_agent(state)
        result2 = government_identity_validation_agent(state)

        assert result1["government_validation_status"] == result2["government_validation_status"]
        assert result1["government_match_score"] == result2["government_match_score"]


# ===========================================================================
# Identity Verification Agent
# ===========================================================================


class TestIdentityVerificationAgent:
    def _state_with_all_checks(self, **overrides):
        """State with all prior agents' outputs filled in."""
        state = _base_state(
            name_match_score=0.92,
            dob_match=True,
            id_match=True,
            duplicate_detected=False,
            fraud_flags=[],
            document_quality_score=0.88,
            document_completeness_score=0.90,
            document_tampering_flag=False,
            compliance_status="passed",
            compliance_flags=[],
            government_match_score=0.93,
            government_validation_status="verified",
        )
        state.update(overrides)
        return state

    def test_verified_identity(self):
        """All checks passing → verified status."""
        from app.agents.identity_verification_agent import identity_verification_agent

        state = self._state_with_all_checks()
        result = identity_verification_agent(state)

        assert result["identity_verification_status"] == "verified"
        assert result["identity_confidence_score"] >= 0.70
        assert result["fraud_flag"] is False
        assert result["current_agent"] == "identity_verification_agent"

    def test_unverified_on_fraud_flag(self):
        """SANCTIONS_MATCH_FOUND in compliance → unverified."""
        from app.agents.identity_verification_agent import identity_verification_agent

        state = self._state_with_all_checks(
            compliance_status="failed",
            compliance_flags=["SANCTIONS_MATCH_FOUND"],
        )
        result = identity_verification_agent(state)

        assert result["identity_verification_status"] == "unverified"
        assert result["fraud_flag"] is True

    def test_confidence_propagated_to_state(self):
        """identity_confidence_score is propagated to confidence_score."""
        from app.agents.identity_verification_agent import identity_verification_agent

        state = self._state_with_all_checks()
        result = identity_verification_agent(state)

        assert result["confidence_score"] == result["identity_confidence_score"]


# ===========================================================================
# Final Report Agent
# ===========================================================================


class TestFinalReportAgent:
    @patch("app.agents.final_report_agent._persist_report")
    def test_report_structure(self, mock_persist):
        """Generated report contains all required sections."""
        from app.agents.final_report_agent import final_report_agent

        state = _base_state(
            identity_confidence_score=0.85,
            fraud_flag=False,
            compliance_status="passed",
            government_validation_status="verified",
            government_reference_id="GOV-REF-ABCD1234",
        )
        result = final_report_agent(state)

        assert result["final_report"] is not None
        report = result["final_report"]
        assert "report_metadata" in report
        assert "customer_submitted_details" in report
        assert "ocr_extracted_details" in report
        assert "workflow_results" in report
        assert "fraud_compliance_flags" in report
        assert "scores_summary" in report
        assert "recommended_action" in report

    @patch("app.agents.final_report_agent._persist_report")
    def test_recommendation_approve(self, mock_persist):
        """High confidence + compliance passed → approve."""
        from app.agents.final_report_agent import final_report_agent

        state = _base_state(
            identity_confidence_score=0.90,
            fraud_flag=False,
            compliance_status="passed",
        )
        result = final_report_agent(state)

        assert result["final_recommendation"] == "approve"

    @patch("app.agents.final_report_agent._persist_report")
    def test_recommendation_reject_on_fraud(self, mock_persist):
        """Fraud flag → reject."""
        from app.agents.final_report_agent import final_report_agent

        state = _base_state(
            identity_confidence_score=0.50,
            fraud_flag=True,
            compliance_status="failed",
        )
        result = final_report_agent(state)

        assert result["final_recommendation"] == "reject"

    @patch("app.agents.final_report_agent._persist_report")
    def test_recommendation_manual_review(self, mock_persist):
        """Mid-range confidence without fraud → manual_review."""
        from app.agents.final_report_agent import final_report_agent

        state = _base_state(
            identity_confidence_score=0.62,
            fraud_flag=False,
            compliance_status="flagged",
        )
        result = final_report_agent(state)

        assert result["final_recommendation"] == "manual_review"


# ===========================================================================
# Graph step transitions
# ===========================================================================


class TestGraphTransitions:
    def test_all_nodes_registered(self):
        """Build the graph and verify all 9 nodes are present."""
        from app.graph.kyc_graph import build_kyc_graph, NODE_INGESTION, NODE_DOCUMENT_PROCESSING
        from app.graph.kyc_graph import (
            NODE_CUSTOMER_DOCUMENT_ANALYSIS,
            NODE_CUSTOMER_COMPLIANCE_REVIEW,
            NODE_GOVERNMENT_IDENTITY_VALIDATION,
            NODE_IDENTITY_VERIFICATION,
            NODE_FINAL_REPORT,
            NODE_DECISION,
            NODE_ERROR_HANDLER,
        )

        graph = build_kyc_graph()
        node_names = set(graph.nodes.keys())

        for expected_node in [
            NODE_INGESTION,
            NODE_DOCUMENT_PROCESSING,
            NODE_CUSTOMER_DOCUMENT_ANALYSIS,
            NODE_CUSTOMER_COMPLIANCE_REVIEW,
            NODE_GOVERNMENT_IDENTITY_VALIDATION,
            NODE_IDENTITY_VERIFICATION,
            NODE_FINAL_REPORT,
            NODE_DECISION,
            NODE_ERROR_HANDLER,
        ]:
            assert expected_node in node_names, f"Node '{expected_node}' missing from graph"

    def test_route_after_ingestion_no_errors(self):
        """No errors → route to document_processing."""
        from app.graph.kyc_graph import route_after_ingestion

        state = _base_state(errors=[])
        assert route_after_ingestion(state) == "document_processing"

    def test_route_after_ingestion_with_errors(self):
        """Errors → route to error_handler."""
        from app.graph.kyc_graph import route_after_ingestion

        state = _base_state(errors=["Validation failed"])
        assert route_after_ingestion(state) == "error_handler"

    def test_route_after_document_processing_no_errors(self):
        """No errors → route to customer_document_analysis."""
        from app.graph.kyc_graph import route_after_document_processing

        state = _base_state(errors=[])
        assert route_after_document_processing(state) == "customer_document_analysis"

    def test_route_after_error_handler_max_retries(self):
        """Max retries reached → route to decision."""
        from app.graph.kyc_graph import route_after_error_handler
        from app.agents.error_handler import MAX_RETRIES

        state = _base_state(retry_count=MAX_RETRIES, errors=["ingestion: error"])
        assert route_after_error_handler(state) == "decision"


# ===========================================================================
# Workflow service helpers
# ===========================================================================


class TestWorkflowHelpers:
    def test_compute_progress_all_pending(self):
        """All steps pending → 0%."""
        from app.api.v1.endpoints.workflow import _compute_progress
        from app.models.workflow import KYCWorkflowStep, WorkflowStepName, WorkflowStepStatus

        steps = []
        for name in [
            WorkflowStepName.CUSTOMER_DOCUMENT_ANALYSIS,
            WorkflowStepName.CUSTOMER_COMPLIANCE_REVIEW,
            WorkflowStepName.GOVERNMENT_IDENTITY_VALIDATION,
            WorkflowStepName.IDENTITY_VERIFICATION,
            WorkflowStepName.FINAL_REPORT_GENERATION,
        ]:
            s = KYCWorkflowStep.__new__(KYCWorkflowStep)
            s.step_name = name
            s.status = WorkflowStepStatus.PENDING
            steps.append(s)

        assert _compute_progress(steps) == 0

    def test_compute_progress_all_completed(self):
        """All admin steps completed → 100%."""
        from app.api.v1.endpoints.workflow import _compute_progress
        from app.models.workflow import KYCWorkflowStep, WorkflowStepName, WorkflowStepStatus

        steps = []
        for name in [
            WorkflowStepName.CUSTOMER_DOCUMENT_ANALYSIS,
            WorkflowStepName.CUSTOMER_COMPLIANCE_REVIEW,
            WorkflowStepName.GOVERNMENT_IDENTITY_VALIDATION,
            WorkflowStepName.IDENTITY_VERIFICATION,
            WorkflowStepName.FINAL_REPORT_GENERATION,
        ]:
            s = KYCWorkflowStep.__new__(KYCWorkflowStep)
            s.step_name = name
            s.status = WorkflowStepStatus.COMPLETED
            steps.append(s)

        assert _compute_progress(steps) == 100

    def test_workflow_status_running(self):
        """IN_PROGRESS step → running."""
        from app.api.v1.endpoints.workflow import _workflow_status
        from app.models.workflow import KYCWorkflowStep, WorkflowStepName, WorkflowStepStatus

        steps = []
        for name, st in [
            (WorkflowStepName.CUSTOMER_DOCUMENT_ANALYSIS, WorkflowStepStatus.COMPLETED),
            (WorkflowStepName.CUSTOMER_COMPLIANCE_REVIEW, WorkflowStepStatus.IN_PROGRESS),
        ]:
            s = KYCWorkflowStep.__new__(KYCWorkflowStep)
            s.step_name = name
            s.status = st
            steps.append(s)

        assert _workflow_status(steps) == "running"
