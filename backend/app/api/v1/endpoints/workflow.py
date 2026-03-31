"""
Admin Workflow Endpoints

POST /admin/workflow/{submission_id}/start       – Start full admin verification pipeline
GET  /admin/workflow/{submission_id}/status      – Poll workflow step statuses
GET  /admin/workflow/{submission_id}/report      – Get final report
POST /admin/workflow/{submission_id}/approve     – Approve case
POST /admin/workflow/{submission_id}/reject      – Reject case
POST /admin/workflow/{submission_id}/manual-review – Mark for manual review
POST /admin/workflow/{submission_id}/notes       – Save admin notes
GET  /admin/workflow/{submission_id}/timeline    – Get timeline events
"""

from __future__ import annotations

import asyncio
import uuid as _uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, require_admin, require_reviewer
from app.core.logging_config import get_logger
from app.models.kyc import KYCStatus, KYCSubmission, RiskLevel
from app.models.user import User
from app.models.workflow import (
    AdminDecisionType,
    KYCAdminDecision,
    KYCFinalReport,
    KYCTimeline,
    KYCWorkflowStep,
    WorkflowStepName,
    WorkflowStepStatus,
)

router = APIRouter(prefix="/admin/workflow", tags=["Admin Workflow"])
logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Request / Response schemas (inline for self-containment)
# ---------------------------------------------------------------------------


class WorkflowStepOut(BaseModel):
    id: str
    step_name: str
    step_order: int
    status: str
    summary: Optional[str]
    score: Optional[float]
    started_at: Optional[datetime]
    completed_at: Optional[datetime]
    duration_ms: Optional[int]
    details: Optional[Dict[str, Any]]

    class Config:
        from_attributes = True


class WorkflowStatusResponse(BaseModel):
    submission_id: str
    workflow_status: str  # pending | running | completed | failed
    progress_pct: int
    steps: List[WorkflowStepOut]
    final_recommendation: Optional[str]
    report_available: bool


class FinalReportResponse(BaseModel):
    submission_id: str
    report: Optional[Dict[str, Any]]
    final_confidence_score: Optional[float]
    recommended_action: Optional[str]
    fraud_detected: bool
    compliance_passed: bool
    government_validated: bool
    identity_verified: bool
    document_quality_score: Optional[float]
    generated_at: Optional[datetime]


class AdminDecisionRequest(BaseModel):
    notes: Optional[str] = Field(None, description="Admin notes / reason for decision")


class AdminNotesRequest(BaseModel):
    notes: str = Field(..., min_length=1, description="Notes to save")


class TimelineEventOut(BaseModel):
    id: str
    event_type: str
    event_title: str
    event_detail: Optional[str]
    actor: Optional[str]
    occurred_at: datetime

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

# Display labels for admin-visible steps
ADMIN_STEP_NAMES = [
    WorkflowStepName.CUSTOMER_DOCUMENT_ANALYSIS.value,
    WorkflowStepName.CUSTOMER_COMPLIANCE_REVIEW.value,
    WorkflowStepName.GOVERNMENT_IDENTITY_VALIDATION.value,
    WorkflowStepName.IDENTITY_VERIFICATION.value,
    WorkflowStepName.FINAL_REPORT_GENERATION.value,
]

STEP_ORDER_MAP = {
    WorkflowStepName.INGESTION.value: 0,
    WorkflowStepName.DOCUMENT_PROCESSING.value: 1,
    WorkflowStepName.CUSTOMER_DOCUMENT_ANALYSIS.value: 2,
    WorkflowStepName.CUSTOMER_COMPLIANCE_REVIEW.value: 3,
    WorkflowStepName.GOVERNMENT_IDENTITY_VALIDATION.value: 4,
    WorkflowStepName.IDENTITY_VERIFICATION.value: 5,
    WorkflowStepName.FINAL_REPORT_GENERATION.value: 6,
    WorkflowStepName.DECISION.value: 7,
}


async def _get_submission_or_404(
    submission_id: UUID, db: AsyncSession
) -> KYCSubmission:
    result = await db.execute(
        select(KYCSubmission).where(KYCSubmission.id == submission_id)
    )
    submission = result.scalar_one_or_none()
    if not submission:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="KYC submission not found.",
        )
    return submission


async def _init_workflow_steps(submission_id: UUID, db: AsyncSession) -> None:
    """Create PENDING step records for all 8 pipeline steps (if not already present)."""
    for step_name_str, order in STEP_ORDER_MAP.items():
        step_enum = WorkflowStepName(step_name_str)
        existing = await db.execute(
            select(KYCWorkflowStep).where(
                KYCWorkflowStep.submission_id == submission_id,
                KYCWorkflowStep.step_name == step_enum,
            )
        )
        if existing.scalar_one_or_none() is None:
            step = KYCWorkflowStep(
                submission_id=submission_id,
                step_name=step_enum,
                step_order=order,
                status=WorkflowStepStatus.PENDING,
            )
            db.add(step)

    timeline = KYCTimeline(
        submission_id=submission_id,
        event_type="WORKFLOW_STARTED",
        event_title="Admin Verification Workflow Started",
        event_detail="Admin initiated the full ID & verification pipeline.",
        actor="admin",
    )
    db.add(timeline)
    await db.commit()


def _compute_progress(steps: List[KYCWorkflowStep]) -> int:
    """Return progress as integer 0-100 based on admin-visible step completion."""
    admin_steps = [s for s in steps if s.step_name.value in ADMIN_STEP_NAMES]
    if not admin_steps:
        return 0
    completed = sum(
        1
        for s in admin_steps
        if s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.FAILED)
    )
    return int((completed / len(admin_steps)) * 100)


def _workflow_status(steps: List[KYCWorkflowStep]) -> str:
    """Derive overall workflow execution status from step records."""
    statuses = {s.status for s in steps}
    if not steps:
        return "pending"
    if WorkflowStepStatus.IN_PROGRESS in statuses:
        return "running"
    if all(
        s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.SKIPPED)
        for s in steps
    ):
        return "completed"
    if WorkflowStepStatus.FAILED in statuses:
        all_complete = all(
            s.status in (WorkflowStepStatus.COMPLETED, WorkflowStepStatus.FAILED, WorkflowStepStatus.SKIPPED)
            for s in steps
        )
        return "completed_with_errors" if all_complete else "running"
    if all(s.status == WorkflowStepStatus.PENDING for s in steps):
        return "pending"
    return "running"


async def _run_workflow_background(submission_id_str: str) -> None:
    """
    Execute the LangGraph KYC pipeline asynchronously in a background task.
    Uses a thread pool since the graph agents are synchronous.
    """
    import concurrent.futures  # noqa: PLC0415
    from app.graph.kyc_graph import get_kyc_graph  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415
    from app.models.kyc import KYCSubmission, KYCStatus  # noqa: PLC0415

    logger.info("Background workflow starting", submission_id=submission_id_str)

    # Fetch submission data needed for graph state
    async with AsyncSessionLocal() as session:
        result = await session.execute(
            select(KYCSubmission).where(
                KYCSubmission.id == _uuid.UUID(submission_id_str)
            )
        )
        submission = result.scalar_one_or_none()
        if not submission:
            logger.error("Workflow background task: submission not found", id=submission_id_str)
            return

        # Eagerly load documents relationship before session is committed/closed
        await session.refresh(submission, attribute_names=["documents"])

        # Build initial graph state
        doc_ids = [str(d.id) for d in (submission.documents or [])]
        form_data = {
            "first_name": submission.applicant_first_name,
            "last_name": submission.applicant_last_name,
            "date_of_birth": (
                submission.applicant_date_of_birth.strftime("%Y-%m-%d")
                if submission.applicant_date_of_birth
                else None
            ),
            "address": submission.applicant_address,
            "id_number": submission.primary_document_number,
            "id_type": submission.primary_document_type.value if submission.primary_document_type else None,
            "nationality": submission.applicant_nationality,
            "phone": submission.applicant_phone,
            "email": submission.applicant_email,
        }

        # Update submission to PROCESSING
        submission.status = KYCStatus.PROCESSING
        submission.processing_started_at = datetime.now(timezone.utc)
        await session.commit()

    initial_state = {
        "kyc_submission_id": submission_id_str,
        "user_id": str(submission.user_id),
        "form_data": form_data,
        "document_ids": doc_ids,
        "current_agent": "start",
        "retry_count": 0,
        "errors": [],
        "ocr_results": [],
        "fraud_flags": [],
        "started_at": datetime.now(timezone.utc).isoformat(),
    }

    try:
        graph = get_kyc_graph()

        # Register the running event loop so _record_step() inside worker
        # threads can schedule DB coroutines back onto it via
        # run_coroutine_threadsafe() instead of creating a new loop that
        # cannot reuse the asyncpg connection pool.
        from app.graph.kyc_graph import _register_main_loop  # noqa: PLC0415
        _register_main_loop(asyncio.get_running_loop())

        def _run_graph():
            return graph.invoke(initial_state)

        loop = asyncio.get_running_loop()
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            await loop.run_in_executor(executor, _run_graph)

        logger.info("Background workflow completed", submission_id=submission_id_str)

    except Exception as exc:
        logger.error(
            "Background workflow failed",
            submission_id=submission_id_str,
            error=str(exc),
            exc_info=True,
        )
        # Mark submission as error state
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KYCSubmission).where(
                    KYCSubmission.id == _uuid.UUID(submission_id_str)
                )
            )
            sub = result.scalar_one_or_none()
            if sub:
                sub.processing_error = str(exc)
                await session.commit()


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/{submission_id}/start",
    status_code=status.HTTP_202_ACCEPTED,
    summary="Start admin verification workflow",
    description=(
        "Trigger the full multi-agent KYC review pipeline for a submission. "
        "Initializes all workflow step records then runs the LangGraph pipeline "
        "in the background. Poll /status to track progress."
    ),
)
async def start_workflow(
    submission_id: UUID,
    background_tasks: BackgroundTasks,
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Kick off the admin verification pipeline for a KYC case."""
    submission = await _get_submission_or_404(submission_id, db)

    # Initialize step records (idempotent)
    await _init_workflow_steps(submission_id, db)

    # Launch graph execution in background
    background_tasks.add_task(_run_workflow_background, str(submission_id))

    logger.info(
        "Admin workflow started",
        submission_id=str(submission_id),
        reviewer_id=str(reviewer.id),
    )

    return {
        "message": "Verification workflow started.",
        "submission_id": str(submission_id),
        "status": "running",
    }


@router.get(
    "/{submission_id}/status",
    response_model=WorkflowStatusResponse,
    summary="Get workflow step statuses",
    description="Poll this endpoint to track live progress of all workflow steps.",
)
async def get_workflow_status(
    submission_id: UUID,
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> WorkflowStatusResponse:
    """Return current status of all workflow steps."""
    await _get_submission_or_404(submission_id, db)

    steps_result = await db.execute(
        select(KYCWorkflowStep)
        .where(KYCWorkflowStep.submission_id == submission_id)
        .order_by(KYCWorkflowStep.step_order)
    )
    steps = list(steps_result.scalars().all())

    report_result = await db.execute(
        select(KYCFinalReport).where(KYCFinalReport.submission_id == submission_id)
    )
    report = report_result.scalar_one_or_none()

    progress = _compute_progress(steps)
    wf_status = _workflow_status(steps)

    step_outs = [
        WorkflowStepOut(
            id=str(s.id),
            step_name=s.step_name.value,
            step_order=s.step_order,
            status=s.status.value,
            summary=s.summary,
            score=s.score,
            started_at=s.started_at,
            completed_at=s.completed_at,
            duration_ms=s.duration_ms,
            details=s.details,
        )
        for s in steps
    ]

    return WorkflowStatusResponse(
        submission_id=str(submission_id),
        workflow_status=wf_status,
        progress_pct=progress,
        steps=step_outs,
        final_recommendation=report.recommended_action if report else None,
        report_available=report is not None,
    )


@router.get(
    "/{submission_id}/report",
    response_model=FinalReportResponse,
    summary="Get the generated KYC final report",
)
async def get_final_report(
    submission_id: UUID,
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> FinalReportResponse:
    """Retrieve the structured KYC report generated by the final report agent."""
    await _get_submission_or_404(submission_id, db)

    result = await db.execute(
        select(KYCFinalReport).where(KYCFinalReport.submission_id == submission_id)
    )
    report = result.scalar_one_or_none()
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Final report not yet generated. Run the workflow first.",
        )

    return FinalReportResponse(
        submission_id=str(submission_id),
        report=report.report_data,
        final_confidence_score=report.final_confidence_score,
        recommended_action=report.recommended_action,
        fraud_detected=report.fraud_detected,
        compliance_passed=report.compliance_passed,
        government_validated=report.government_validated,
        identity_verified=report.identity_verified,
        document_quality_score=report.document_quality_score,
        generated_at=report.generated_at,
    )


@router.post(
    "/{submission_id}/approve",
    status_code=status.HTTP_200_OK,
    summary="Approve a KYC case",
)
async def approve_case(
    submission_id: UUID,
    body: AdminDecisionRequest,
    admin: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Admin approves the KYC submission."""
    return await _record_admin_decision(
        submission_id=submission_id,
        decision_type=AdminDecisionType.APPROVED,
        kyc_status=KYCStatus.APPROVED,
        admin=admin,
        notes=body.notes,
        db=db,
    )


@router.post(
    "/{submission_id}/reject",
    status_code=status.HTTP_200_OK,
    summary="Reject a KYC case",
)
async def reject_case(
    submission_id: UUID,
    body: AdminDecisionRequest,
    admin: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Admin rejects the KYC submission."""
    return await _record_admin_decision(
        submission_id=submission_id,
        decision_type=AdminDecisionType.REJECTED,
        kyc_status=KYCStatus.REJECTED,
        admin=admin,
        notes=body.notes,
        db=db,
    )


@router.post(
    "/{submission_id}/manual-review",
    status_code=status.HTTP_200_OK,
    summary="Mark a KYC case for manual review",
)
async def manual_review_case(
    submission_id: UUID,
    body: AdminDecisionRequest,
    admin: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Admin marks the KYC submission for manual review."""
    return await _record_admin_decision(
        submission_id=submission_id,
        decision_type=AdminDecisionType.MANUAL_REVIEW,
        kyc_status=KYCStatus.UNDER_REVIEW,
        admin=admin,
        notes=body.notes,
        db=db,
    )


@router.post(
    "/{submission_id}/notes",
    status_code=status.HTTP_200_OK,
    summary="Save admin notes for a KYC case",
)
async def save_admin_notes(
    submission_id: UUID,
    body: AdminNotesRequest,
    admin: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> Dict[str, Any]:
    """Save or update admin notes on a KYC submission."""
    submission = await _get_submission_or_404(submission_id, db)
    submission.reviewer_notes = body.notes
    submission.reviewer_id = admin.id

    timeline = KYCTimeline(
        submission_id=submission_id,
        event_type="ADMIN_NOTES_SAVED",
        event_title="Admin Notes Updated",
        event_detail=body.notes[:200] + "…" if len(body.notes) > 200 else body.notes,
        actor=admin.username or admin.email,
    )
    db.add(timeline)
    await db.commit()

    return {"message": "Notes saved.", "submission_id": str(submission_id)}


@router.get(
    "/{submission_id}/timeline",
    response_model=List[TimelineEventOut],
    summary="Get KYC case timeline / journey log",
)
async def get_timeline(
    submission_id: UUID,
    reviewer: User = Depends(require_reviewer),
    db: AsyncSession = Depends(get_db),
) -> List[TimelineEventOut]:
    """Return the ordered timeline of events for a KYC case."""
    await _get_submission_or_404(submission_id, db)

    result = await db.execute(
        select(KYCTimeline)
        .where(KYCTimeline.submission_id == submission_id)
        .order_by(KYCTimeline.occurred_at)
    )
    events = result.scalars().all()

    return [
        TimelineEventOut(
            id=str(e.id),
            event_type=e.event_type,
            event_title=e.event_title,
            event_detail=e.event_detail,
            actor=e.actor,
            occurred_at=e.occurred_at,
        )
        for e in events
    ]


# ---------------------------------------------------------------------------
# Internal helper
# ---------------------------------------------------------------------------


async def _record_admin_decision(
    submission_id: UUID,
    decision_type: AdminDecisionType,
    kyc_status: KYCStatus,
    admin: User,
    notes: Optional[str],
    db: AsyncSession,
) -> Dict[str, Any]:
    """Persist admin decision and update submission status."""
    submission = await _get_submission_or_404(submission_id, db)

    # Update submission status
    submission.status = kyc_status
    submission.reviewer_id = admin.id
    submission.reviewed_at = datetime.now(timezone.utc)
    if notes:
        submission.reviewer_notes = notes

    # Record decision
    decision = KYCAdminDecision(
        submission_id=submission_id,
        admin_id=admin.id,
        decision_type=decision_type,
        notes=notes,
        decided_at=datetime.now(timezone.utc),
    )
    db.add(decision)

    # Timeline
    label_map = {
        AdminDecisionType.APPROVED: "Case Approved",
        AdminDecisionType.REJECTED: "Case Rejected",
        AdminDecisionType.MANUAL_REVIEW: "Escalated for Manual Review",
    }
    timeline = KYCTimeline(
        submission_id=submission_id,
        event_type="ADMIN_DECISION",
        event_title=label_map[decision_type],
        event_detail=notes or f"Decision: {decision_type.value}",
        actor=admin.username or admin.email,
        event_metadata={"decision": decision_type.value, "admin_id": str(admin.id)},
    )
    db.add(timeline)

    await db.commit()

    logger.info(
        "Admin decision recorded",
        submission_id=str(submission_id),
        decision=decision_type.value,
        admin_id=str(admin.id),
    )

    return {
        "message": f"Case {decision_type.value}.",
        "submission_id": str(submission_id),
        "decision": decision_type.value,
        "new_status": kyc_status.value,
    }
