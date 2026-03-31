"""
KYC LangGraph Pipeline (Extended Admin Review)

Full pipeline topology:

  START
    → ingestion
    → document_processing
    → customer_document_analysis
    → customer_compliance_review
    → government_identity_validation
    → identity_verification        (consolidated identity agent)
    → final_report_generation
    → decision
    → END

Error handler node handles retries for the early pipeline stages
(ingestion, document_processing). The new admin-review agents
(analysis, compliance, government, identity_verification, final_report)
are non-retryable by default – on failure they write degraded output
and processing continues so the admin still gets a partial report.

The graph persists workflow step records to KYCWorkflowStep and
KYCTimeline as each agent runs.
"""

from __future__ import annotations

import asyncio
import threading as _threading
from datetime import datetime, timezone
from typing import Literal

# ---------------------------------------------------------------------------
# Main-event-loop reference for cross-thread coroutine scheduling
# ---------------------------------------------------------------------------
# The graph agents run in a ThreadPoolExecutor while the FastAPI event loop
# is alive on the main thread.  asyncpg connection pools are bound to the
# loop that created them, so we must schedule DB coroutines back onto that
# loop via run_coroutine_threadsafe() rather than creating a fresh loop with
# asyncio.run() inside the worker thread.

_main_loop_ref: asyncio.AbstractEventLoop | None = None
_main_loop_lock = _threading.Lock()


def _register_main_loop(loop: asyncio.AbstractEventLoop) -> None:
    """Call once from the async context (before run_in_executor) to register the
    running event loop so worker-thread step-recording can schedule onto it."""
    global _main_loop_ref
    with _main_loop_lock:
        _main_loop_ref = loop

from langgraph.graph import END, START, StateGraph

from app.agents.customer_compliance_review_agent import customer_compliance_review_agent
from app.agents.customer_document_analysis_agent import customer_document_analysis_agent
from app.agents.decision_agent import decision_agent
from app.agents.document_processing_agent import document_processing_agent
from app.agents.error_handler import MAX_RETRIES, error_handler
from app.agents.final_report_agent import final_report_agent
from app.agents.government_identity_validation_agent import government_identity_validation_agent
from app.agents.identity_verification_agent import identity_verification_agent
from app.agents.ingestion_agent import ingestion_agent
from app.agents.state import KYCAgentState
from app.agents.verification_agent import verification_agent
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Node name constants
# ---------------------------------------------------------------------------

NODE_INGESTION = "ingestion"
NODE_DOCUMENT_PROCESSING = "document_processing"
NODE_CUSTOMER_DOCUMENT_ANALYSIS = "customer_document_analysis"
NODE_CUSTOMER_COMPLIANCE_REVIEW = "customer_compliance_review"
NODE_GOVERNMENT_IDENTITY_VALIDATION = "government_identity_validation"
NODE_IDENTITY_VERIFICATION = "identity_verification"
NODE_FINAL_REPORT = "final_report_generation"
NODE_DECISION = "kyc_decision"
NODE_ERROR_HANDLER = "error_handler"

# Display labels used in the UI / timeline
STEP_LABELS = {
    NODE_INGESTION: "Ingestion",
    NODE_DOCUMENT_PROCESSING: "Document Processing",
    NODE_CUSTOMER_DOCUMENT_ANALYSIS: "Customer Document Analysis",
    NODE_CUSTOMER_COMPLIANCE_REVIEW: "Customer Compliance Review",
    NODE_GOVERNMENT_IDENTITY_VALIDATION: "Government Identity Validation",
    NODE_IDENTITY_VERIFICATION: "Identity Verification",
    NODE_FINAL_REPORT: "Final Report Generation",
    NODE_DECISION: "Decision",
}

# Ordered list of all admin-visible steps (subset shown in UI)
ADMIN_WORKFLOW_STEPS = [
    NODE_CUSTOMER_DOCUMENT_ANALYSIS,
    NODE_CUSTOMER_COMPLIANCE_REVIEW,
    NODE_GOVERNMENT_IDENTITY_VALIDATION,
    NODE_IDENTITY_VERIFICATION,
    NODE_FINAL_REPORT,
]

# ---------------------------------------------------------------------------
# Workflow step DB persistence helper
# ---------------------------------------------------------------------------


def _record_step(
    submission_id: str,
    step_name: str,
    status: str,
    summary: Optional[str] = None,
    details: Optional[dict] = None,
    score: Optional[float] = None,
    started_at: Optional[datetime] = None,
    completed_at: Optional[datetime] = None,
) -> None:
    """
    Upsert a KYCWorkflowStep record for the given submission and step.
    Also appends a KYCTimeline entry.
    Non-blocking: runs in a thread pool to avoid blocking the sync agent.
    """
    from sqlalchemy import select  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.workflow import (  # noqa: PLC0415
        KYCWorkflowStep, KYCTimeline,
        WorkflowStepName, WorkflowStepStatus,
    )
    import uuid as _uuid  # noqa: PLC0415

    step_order_map = {
        NODE_INGESTION: 0,
        NODE_DOCUMENT_PROCESSING: 1,
        NODE_CUSTOMER_DOCUMENT_ANALYSIS: 2,
        NODE_CUSTOMER_COMPLIANCE_REVIEW: 3,
        NODE_GOVERNMENT_IDENTITY_VALIDATION: 4,
        NODE_IDENTITY_VERIFICATION: 5,
        NODE_FINAL_REPORT: 6,
        NODE_DECISION: 7,
    }

    status_map = {
        "pending": WorkflowStepStatus.PENDING,
        "in_progress": WorkflowStepStatus.IN_PROGRESS,
        "completed": WorkflowStepStatus.COMPLETED,
        "failed": WorkflowStepStatus.FAILED,
        "skipped": WorkflowStepStatus.SKIPPED,
    }

    step_name_map = {v.value: v for v in WorkflowStepName}
    step_enum = step_name_map.get(step_name)
    if not step_enum:
        return  # Unknown step – skip

    duration_ms = None
    if started_at and completed_at:
        duration_ms = int((completed_at - started_at).total_seconds() * 1000)

    async def _save():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KYCWorkflowStep).where(
                    KYCWorkflowStep.submission_id == _uuid.UUID(submission_id),
                    KYCWorkflowStep.step_name == step_enum,
                )
            )
            step_rec = result.scalar_one_or_none()
            if step_rec is None:
                step_rec = KYCWorkflowStep(
                    submission_id=_uuid.UUID(submission_id),
                    step_name=step_enum,
                    step_order=step_order_map.get(step_name, 99),
                )
                session.add(step_rec)

            step_rec.status = status_map.get(status, WorkflowStepStatus.IN_PROGRESS)
            step_rec.summary = summary
            step_rec.details = details
            step_rec.score = score
            if started_at and step_rec.started_at is None:
                step_rec.started_at = started_at
            if completed_at:
                step_rec.completed_at = completed_at
            if duration_ms:
                step_rec.duration_ms = duration_ms

            # Timeline entry
            event_type = "STEP_COMPLETED" if status == "completed" else (
                "STEP_FAILED" if status == "failed" else "STEP_STARTED"
            )
            label = STEP_LABELS.get(step_name, step_name)
            timeline = KYCTimeline(
                submission_id=_uuid.UUID(submission_id),
                event_type=event_type,
                event_title=f"{label} {status.replace('_', ' ').title()}",
                event_detail=summary,
                actor=f"{step_name}_agent",
                event_metadata={"step_name": step_name, "score": score},
            )
            session.add(timeline)

            await session.commit()

    try:
        loop = _main_loop_ref
        if loop is not None and loop.is_running():
            # Schedule the coroutine on the main event loop from this worker thread.
            # This is necessary because asyncpg connection pools are bound to the
            # loop that created them; using asyncio.run() here would create a fresh
            # loop that cannot reuse those connections.
            future = asyncio.run_coroutine_threadsafe(_save(), loop)
            future.result(timeout=15)
        else:
            # Fallback: no registered loop (e.g. running outside FastAPI in tests).
            asyncio.run(_save())
    except Exception as exc:
        logger.warning("Workflow step DB record failed", step=step_name, error=str(exc), exc_info=True)


# Needed for Optional hint above
from typing import Optional  # noqa: E402


# ---------------------------------------------------------------------------
# Agent wrappers that record step status before/after execution
# ---------------------------------------------------------------------------


def _wrap_admin_agent(agent_fn, step_name: str):
    """
    Return a wrapped version of agent_fn that records workflow step status.

    Records IN_PROGRESS before the agent runs, then COMPLETED or FAILED after.
    """
    def wrapped(state: KYCAgentState) -> KYCAgentState:
        submission_id = state.get("kyc_submission_id", "")
        started = datetime.now(timezone.utc)

        # Mark step as in_progress
        _record_step(
            submission_id=submission_id,
            step_name=step_name,
            status="in_progress",
            started_at=started,
        )

        try:
            new_state = agent_fn(state)
            completed = datetime.now(timezone.utc)

            # Extract relevant summary/score from new state based on step
            summary, score = _extract_step_output(new_state, step_name)

            _record_step(
                submission_id=submission_id,
                step_name=step_name,
                status="completed",
                summary=summary,
                score=score,
                started_at=started,
                completed_at=completed,
            )
            return new_state

        except Exception as exc:
            completed = datetime.now(timezone.utc)
            _record_step(
                submission_id=submission_id,
                step_name=step_name,
                status="failed",
                summary=str(exc),
                started_at=started,
                completed_at=completed,
            )
            raise

    wrapped.__name__ = agent_fn.__name__
    return wrapped


def _extract_step_output(state: KYCAgentState, step_name: str):
    """Return (summary, score) tuple for the completed step."""
    if step_name == NODE_CUSTOMER_DOCUMENT_ANALYSIS:
        return (
            state.get("document_analysis_summary"),
            state.get("document_quality_score"),
        )
    if step_name == NODE_CUSTOMER_COMPLIANCE_REVIEW:
        return (
            state.get("compliance_summary"),
            None,
        )
    if step_name == NODE_GOVERNMENT_IDENTITY_VALIDATION:
        return (
            state.get("government_validation_summary"),
            state.get("government_match_score"),
        )
    if step_name == NODE_IDENTITY_VERIFICATION:
        return (
            state.get("identity_verification_summary"),
            state.get("identity_confidence_score"),
        )
    if step_name == NODE_FINAL_REPORT:
        rec = state.get("final_recommendation")
        return (
            f"Final report generated. Recommendation: {rec}." if rec else "Report generated.",
            state.get("identity_confidence_score"),
        )
    return (None, None)


# ---------------------------------------------------------------------------
# Routing helpers
# ---------------------------------------------------------------------------

_RETRY_TARGETS = {
    NODE_INGESTION: NODE_INGESTION,
    NODE_DOCUMENT_PROCESSING: NODE_DOCUMENT_PROCESSING,
}


def route_after_ingestion(
    state: KYCAgentState,
) -> Literal["document_processing", "error_handler"]:
    if state.get("errors"):
        return NODE_ERROR_HANDLER
    return NODE_DOCUMENT_PROCESSING


def route_after_document_processing(
    state: KYCAgentState,
) -> Literal["customer_document_analysis", "error_handler"]:
    if state.get("errors"):
        return NODE_ERROR_HANDLER
    return NODE_CUSTOMER_DOCUMENT_ANALYSIS


def route_after_error_handler(
    state: KYCAgentState,
) -> Literal[
    "ingestion",
    "document_processing",
    "customer_document_analysis",
    "kyc_decision",
]:
    if state.get("decision") is not None:
        return NODE_DECISION
    retry_count = state.get("retry_count") or 0
    if retry_count >= MAX_RETRIES:
        # After exhausting retries, proceed to the admin-review pipeline so the
        # admin always gets a (possibly partial) report rather than jumping
        # straight to decision and leaving all workflow steps as PENDING.
        return NODE_CUSTOMER_DOCUMENT_ANALYSIS
    errors = state.get("errors") or []
    for err in reversed(errors):
        for agent_name in _RETRY_TARGETS:
            if agent_name in err:
                return _RETRY_TARGETS[agent_name]
    return NODE_INGESTION


# ---------------------------------------------------------------------------
# Graph builder
# ---------------------------------------------------------------------------


def build_kyc_graph() -> StateGraph:
    """Construct the extended KYC StateGraph (uncompiled)."""

    graph = StateGraph(KYCAgentState)

    # Core pipeline nodes (unchanged)
    graph.add_node(NODE_INGESTION, ingestion_agent)
    graph.add_node(NODE_DOCUMENT_PROCESSING, document_processing_agent)
    graph.add_node(NODE_ERROR_HANDLER, error_handler)

    # New admin-review pipeline nodes (wrapped for step tracking)
    graph.add_node(
        NODE_CUSTOMER_DOCUMENT_ANALYSIS,
        _wrap_admin_agent(customer_document_analysis_agent, NODE_CUSTOMER_DOCUMENT_ANALYSIS),
    )
    graph.add_node(
        NODE_CUSTOMER_COMPLIANCE_REVIEW,
        _wrap_admin_agent(customer_compliance_review_agent, NODE_CUSTOMER_COMPLIANCE_REVIEW),
    )
    graph.add_node(
        NODE_GOVERNMENT_IDENTITY_VALIDATION,
        _wrap_admin_agent(government_identity_validation_agent, NODE_GOVERNMENT_IDENTITY_VALIDATION),
    )

    # Identity verification wraps the original verification_agent AND the new
    # identity_verification_agent (runs both in sequence inside one node)
    def combined_identity_verification(state: KYCAgentState) -> KYCAgentState:
        """Run legacy verification then consolidated identity verification."""
        state = verification_agent(state)
        state = identity_verification_agent(state)
        return state

    graph.add_node(
        NODE_IDENTITY_VERIFICATION,
        _wrap_admin_agent(combined_identity_verification, NODE_IDENTITY_VERIFICATION),
    )
    graph.add_node(
        NODE_FINAL_REPORT,
        _wrap_admin_agent(final_report_agent, NODE_FINAL_REPORT),
    )
    graph.add_node(NODE_DECISION, decision_agent)

    # Entry point
    graph.add_edge(START, NODE_INGESTION)

    # Conditional routing for early pipeline
    graph.add_conditional_edges(
        NODE_INGESTION,
        route_after_ingestion,
        {
            NODE_DOCUMENT_PROCESSING: NODE_DOCUMENT_PROCESSING,
            NODE_ERROR_HANDLER: NODE_ERROR_HANDLER,
        },
    )

    graph.add_conditional_edges(
        NODE_DOCUMENT_PROCESSING,
        route_after_document_processing,
        {
            NODE_CUSTOMER_DOCUMENT_ANALYSIS: NODE_CUSTOMER_DOCUMENT_ANALYSIS,
            NODE_ERROR_HANDLER: NODE_ERROR_HANDLER,
        },
    )

    graph.add_conditional_edges(
        NODE_ERROR_HANDLER,
        route_after_error_handler,
        {
            NODE_INGESTION: NODE_INGESTION,
            NODE_DOCUMENT_PROCESSING: NODE_DOCUMENT_PROCESSING,
            NODE_CUSTOMER_DOCUMENT_ANALYSIS: NODE_CUSTOMER_DOCUMENT_ANALYSIS,
            NODE_DECISION: NODE_DECISION,
        },
    )

    # Linear chain for admin-review agents (no error routing – they degrade gracefully)
    graph.add_edge(NODE_CUSTOMER_DOCUMENT_ANALYSIS, NODE_CUSTOMER_COMPLIANCE_REVIEW)
    graph.add_edge(NODE_CUSTOMER_COMPLIANCE_REVIEW, NODE_GOVERNMENT_IDENTITY_VALIDATION)
    graph.add_edge(NODE_GOVERNMENT_IDENTITY_VALIDATION, NODE_IDENTITY_VERIFICATION)
    graph.add_edge(NODE_IDENTITY_VERIFICATION, NODE_FINAL_REPORT)
    graph.add_edge(NODE_FINAL_REPORT, NODE_DECISION)

    # Decision is always terminal
    graph.add_edge(NODE_DECISION, END)

    return graph


# ---------------------------------------------------------------------------
# Compiled graph – module-level singleton
# ---------------------------------------------------------------------------

_compiled_graph = None


def get_kyc_graph():
    """
    Return the compiled KYC graph, building it lazily on first call.
    """
    global _compiled_graph
    if _compiled_graph is None:
        logger.info("Compiling KYC LangGraph pipeline (extended admin-review)")
        raw_graph = build_kyc_graph()
        _compiled_graph = raw_graph.compile()
        logger.info("KYC LangGraph pipeline compiled successfully")
    return _compiled_graph
