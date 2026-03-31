"""
KYC Agent State - TypedDict definition for LangGraph state machine.

Defines the complete state object that flows through the KYC verification
pipeline, carrying input data, intermediate results, and final decisions.

Extended to include the full admin review pipeline:
  Ingestion → Document Processing → Customer Document Analysis →
  Customer Compliance Review → Government Identity Validation →
  Identity Verification → Final Report Generation → Decision
"""

from typing import Any, Dict, List, Optional, TypedDict


class KYCAgentState(TypedDict):
    """
    Complete state object for the KYC LangGraph pipeline.

    This TypedDict is passed between all agent nodes in the graph.
    Each agent reads from and writes to specific fields, building up
    the verification result progressively.
    """

    # -------------------------------------------------------------------------
    # Input Fields
    # -------------------------------------------------------------------------
    kyc_submission_id: str
    """UUID string of the KYCSubmission database record."""

    user_id: str
    """UUID string of the user who owns this submission."""

    form_data: Dict[str, Any]
    """
    Applicant-submitted form data. Expected keys:
    - first_name (str)
    - last_name (str)
    - date_of_birth (str, ISO 8601: YYYY-MM-DD)
    - address (str)
    - id_number (str)
    - id_type (str): passport | national_id | drivers_license
    - nationality (str, optional)
    - phone (str, optional)
    - email (str, optional)
    """

    document_ids: List[str]
    """List of Document UUID strings associated with this submission."""

    # -------------------------------------------------------------------------
    # Processing Control Fields
    # -------------------------------------------------------------------------
    current_agent: str
    """Name of the agent that most recently processed this state."""

    retry_count: int
    """Number of times the error handler has retried processing."""

    errors: List[str]
    """Accumulated list of error messages encountered during processing."""

    # -------------------------------------------------------------------------
    # OCR / Document Extraction Results
    # -------------------------------------------------------------------------
    ocr_results: List[Dict[str, Any]]
    """
    Raw OCR results per document. Each entry contains:
    - document_id (str)
    - raw_text (str)
    - confidence (float)
    - processing_time_ms (int)
    - error (str | None)
    """

    extracted_name: Optional[str]
    """Full name extracted from the primary identity document."""

    extracted_dob: Optional[str]
    """Date of birth extracted from document (normalized to YYYY-MM-DD)."""

    extracted_id_number: Optional[str]
    """Document/ID number extracted from the document."""

    extracted_address: Optional[str]
    """Address extracted from the document (if present)."""

    # -------------------------------------------------------------------------
    # Verification / Matching Results
    # -------------------------------------------------------------------------
    name_match_score: Optional[float]
    """Fuzzy match score (0.0-1.0) between form name and OCR-extracted name."""

    dob_match: Optional[bool]
    """Whether the submitted DOB matches the OCR-extracted DOB."""

    id_match: Optional[bool]
    """Whether the submitted ID number matches the OCR-extracted ID number."""

    fraud_flags: List[str]
    """
    List of fraud indicator strings. Examples:
    - NAME_MISMATCH
    - DOB_MISMATCH
    - ID_FORMAT_INVALID
    - DUPLICATE_SUBMISSION
    - LOW_OCR_CONFIDENCE
    - ADDRESS_MISMATCH
    """

    duplicate_detected: Optional[bool]
    """Whether a duplicate submission was found in the database."""

    # -------------------------------------------------------------------------
    # Customer Document Analysis Agent Output
    # -------------------------------------------------------------------------
    document_analysis_status: Optional[str]
    """Status of document analysis: completed | failed | skipped."""

    document_quality_score: Optional[float]
    """Document image quality score (0.0-1.0). Low scores indicate poor quality."""

    document_tampering_flag: Optional[bool]
    """Whether tampering indicators were found in the document."""

    document_type_detected: Optional[str]
    """Document type detected by the analysis agent."""

    document_completeness_score: Optional[float]
    """How complete the document fields are (0.0-1.0)."""

    document_analysis_summary: Optional[str]
    """Human-readable summary of the document analysis."""

    document_analysis_details: Optional[Dict[str, Any]]
    """Detailed per-field analysis results."""

    # -------------------------------------------------------------------------
    # Customer Compliance Review Agent Output
    # -------------------------------------------------------------------------
    compliance_status: Optional[str]
    """Compliance check result: passed | flagged | failed."""

    compliance_flags: Optional[List[str]]
    """
    List of compliance flag strings. Examples:
    - MISSING_MANDATORY_FIELDS
    - HIGH_RISK_NATIONALITY
    - SANCTIONS_MATCH_FOUND
    - PEP_MATCH_FOUND
    - UNSUPPORTED_COUNTRY
    """

    compliance_summary: Optional[str]
    """Human-readable compliance review summary."""

    compliance_details: Optional[Dict[str, Any]]
    """Detailed compliance check results including individual rule outcomes."""

    pep_result: Optional[bool]
    """Politically Exposed Person check result from compliance agent."""

    sanctions_result: Optional[bool]
    """Sanctions screening result from compliance agent."""

    # -------------------------------------------------------------------------
    # Government Identity Validation Agent Output
    # -------------------------------------------------------------------------
    government_validation_status: Optional[str]
    """Government validation result: verified | not_verified | error."""

    government_match_score: Optional[float]
    """How closely submitted details matched government records (0.0-1.0)."""

    government_reference_id: Optional[str]
    """Mock government validation reference ID (e.g. GOV-REF-XXXXXXXX)."""

    government_validation_summary: Optional[str]
    """Human-readable summary of government identity validation."""

    government_validation_details: Optional[Dict[str, Any]]
    """Detailed per-field comparison with government data."""

    # -------------------------------------------------------------------------
    # Identity Verification Agent Output (consolidated)
    # -------------------------------------------------------------------------
    identity_verification_status: Optional[str]
    """Final identity verification status: verified | unverified | inconclusive."""

    identity_confidence_score: Optional[float]
    """Consolidated identity confidence score (0.0-1.0) from all checks."""

    fraud_flag: Optional[bool]
    """Whether the identity verification flagged potential fraud."""

    identity_verification_summary: Optional[str]
    """Human-readable identity verification summary."""

    identity_verification_details: Optional[Dict[str, Any]]
    """Detailed breakdown of all component scores used in identity verification."""

    # -------------------------------------------------------------------------
    # Final Report Generation Agent Output
    # -------------------------------------------------------------------------
    final_report: Optional[Dict[str, Any]]
    """
    Structured KYC report generated for admin review. Includes:
    - customer_submitted_details
    - ocr_extracted_details
    - workflow_results (per-agent summaries)
    - fraud_compliance_flags
    - final_confidence_score
    - recommended_action
    """

    final_recommendation: Optional[str]
    """Recommended action from the report agent: approve | reject | manual_review."""

    report_generated_at: Optional[str]
    """ISO 8601 timestamp when the final report was generated."""

    # -------------------------------------------------------------------------
    # Workflow Step Tracking
    # -------------------------------------------------------------------------
    workflow_steps: Optional[List[Dict[str, Any]]]
    """
    Ordered list of workflow step execution records.
    Each entry: { step_name, status, started_at, completed_at, summary, details }
    """

    # -------------------------------------------------------------------------
    # Decision Fields
    # -------------------------------------------------------------------------
    confidence_score: Optional[float]
    """Overall verification confidence score (0.0-1.0)."""

    risk_level: Optional[str]
    """Risk classification: LOW | MEDIUM | HIGH | CRITICAL."""

    decision: Optional[str]
    """Final KYC decision: APPROVED | REJECTED | MANUAL_REVIEW."""

    decision_reason: Optional[str]
    """Human-readable explanation of the decision."""

    # -------------------------------------------------------------------------
    # Metadata
    # -------------------------------------------------------------------------
    started_at: str
    """ISO 8601 timestamp when processing started."""

    completed_at: Optional[str]
    """ISO 8601 timestamp when processing completed."""

    processing_time_ms: Optional[int]
    """Total end-to-end processing duration in milliseconds."""
