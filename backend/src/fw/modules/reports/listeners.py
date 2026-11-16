"""Event listeners for Reports module (month-end auto-run triggers)."""

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.events import PayrollRunApproved, PayrollRunCreated, event_bus
from fw.modules.reports.service import ReportService

logger = structlog.get_logger(__name__)


async def handle_payroll_run_created(event: PayrollRunCreated, session: AsyncSession) -> None:
    """When a DRAFT payroll run is created or re-run, auto-generate the 11 month-end reports."""
    if not event.payroll_run_id:
        return

    logger.info("handling_payroll_run_created_for_reports", run_id=str(event.payroll_run_id))
    try:
        await ReportService.generate_month_end_reports(
            session=session,
            payroll_run_id=event.payroll_run_id,
            is_approval=False,
            generated_by_user="system",
        )
    except Exception as e:
        logger.error(
            "month_end_reports_draft_failed", error=str(e), run_id=str(event.payroll_run_id)
        )


async def handle_payroll_run_approved(event: PayrollRunApproved, session: AsyncSession) -> None:
    """When a payroll run is approved, generate the final immutable month-end reports."""
    if not event.payroll_run_id:
        return

    logger.info("handling_payroll_run_approved_for_reports", run_id=str(event.payroll_run_id))
    try:
        await ReportService.generate_month_end_reports(
            session=session,
            payroll_run_id=event.payroll_run_id,
            is_approval=True,
            generated_by_user="system",
        )
    except Exception as e:
        logger.error(
            "month_end_reports_approved_failed", error=str(e), run_id=str(event.payroll_run_id)
        )


_registered = False


def register_reports_listeners() -> None:
    """Register reports event listeners with the domain event bus."""
    global _registered
    if not _registered:
        event_bus.subscribe_sync(PayrollRunCreated, handle_payroll_run_created)
        event_bus.subscribe_sync(PayrollRunApproved, handle_payroll_run_approved)
        _registered = True
