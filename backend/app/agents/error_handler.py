"""
KYC Error Handler Node

Handles failures that occur within any agent in the LangGraph pipeline.
Responsibilities:
  - Record the error in state
  - Increment the retry counter
  - Log the failure with context
  - If retries are exhausted, route to the decision agent with a
    MANUAL_REVIEW outcome so no submission is silently dropped
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.agents.state import KYCAgentState
from app.core.logging_config import get_logger

logger = get_logger(__name__)

# Maximum number of times the error handler will allow a retry before
# forcing the pipeline to the decision node with MANUAL_REVIEW.
MAX_RETRIES = 3


def error_handler(state: KYCAgentState) -> KYCAgentState:
    """
    LangGraph node: catch agent failures, implement retry logic, and
    escalate to MANUAL_REVIEW after MAX_RETRIES attempts.

    Reads:
        state["retry_count"]
        state["errors"]
        state["current_agent"]

    Writes:
        state["retry_count"]       – incremented
        state["errors"]            – new error details appended
        state["current_agent"]     – "error_handler"
        state["decision"]          – set to MANUAL_REVIEW if max retries reached
        state["decision_reason"]   – explanation when escalating
        state["risk_level"]        – set to HIGH when escalating
        state["completed_at"]      – set when escalating
    """
    new_state: KYCAgentState = dict(state)  # type: ignore[assignment]

    retry_count: int = state.get("retry_count") or 0
    errors: List[str] = list(state.get("errors") or [])
    failed_agent: str = state.get("current_agent") or "unknown"

    new_state["current_agent"] = "error_handler"
    new_state["retry_count"] = retry_count + 1

    logger.warning(
        "Error handler invoked",
        submission_id=state.get("kyc_submission_id"),
        failed_agent=failed_agent,
        retry_count=retry_count,
        error_count=len(errors),
        recent_errors=errors[-3:] if errors else [],
    )

    if retry_count >= MAX_RETRIES:
        # ----------------------------------------------------------------
        # Exhausted retries – escalate to manual review
        # ----------------------------------------------------------------
        escalation_reason = (
            f"Automated processing failed after {retry_count} attempt(s) "
            f"(agent: {failed_agent}). "
            f"Last errors: {'; '.join(errors[-3:]) if errors else 'unknown'}. "
            "Escalated to manual review for human evaluation."
        )

        new_state["decision"] = "MANUAL_REVIEW"
        new_state["risk_level"] = "HIGH"
        new_state["decision_reason"] = escalation_reason
        new_state["completed_at"] = datetime.now(timezone.utc).isoformat()

        # Ensure partial confidence score doesn't mislead reviewers
        if new_state.get("confidence_score") is None:
            new_state["confidence_score"] = 0.0

        # Ensure fraud_flags is a list (may be None if verification never ran)
        if new_state.get("fraud_flags") is None:
            new_state["fraud_flags"] = []

        logger.error(
            "Max retries exhausted – escalating to MANUAL_REVIEW",
            submission_id=state.get("kyc_submission_id"),
            retry_count=retry_count,
            failed_agent=failed_agent,
        )

        # Attempt to persist escalation in DB
        _persist_escalation(
            submission_id=state.get("kyc_submission_id", ""),
            reason=escalation_reason,
            errors=errors,
        )
    else:
        logger.info(
            "Error handler: scheduling retry",
            submission_id=state.get("kyc_submission_id"),
            attempt=retry_count + 1,
            max_retries=MAX_RETRIES,
        )
        # Clear the errors list so the retry starts fresh for that agent
        # (preserving prior errors for audit by prepending a retry marker)
        errors.append(
            f"[retry {retry_count + 1}/{MAX_RETRIES}] Retrying after "
            f"failure in agent '{failed_agent}'."
        )

    new_state["errors"] = errors
    return new_state


def _persist_escalation(
    submission_id: str,
    reason: str,
    errors: List[str],
) -> None:
    """Update the DB record to UNDER_REVIEW status on escalation."""
    import asyncio  # noqa: PLC0415
    from sqlalchemy import select  # noqa: PLC0415
    from app.core.database import AsyncSessionLocal  # noqa: PLC0415
    from app.models.kyc import KYCSubmission, KYCStatus, RiskLevel  # noqa: PLC0415

    async def _update():
        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(KYCSubmission).where(KYCSubmission.id == submission_id)
            )
            submission = result.scalar_one_or_none()
            if submission is None:
                return
            submission.status = KYCStatus.UNDER_REVIEW
            submission.status_reason = reason
            submission.risk_level = RiskLevel.HIGH
            submission.processing_error = "\n".join(errors[-10:])
            await session.commit()

    try:
        try:
            asyncio.get_running_loop()
            import concurrent.futures  # noqa: PLC0415

            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(asyncio.run, _update())
                future.result(timeout=10)
        except RuntimeError:
            asyncio.run(_update())
    except Exception as exc:
        logger.error(
            "Error handler: DB escalation update failed",
            submission_id=submission_id,
            error=str(exc),
        )
