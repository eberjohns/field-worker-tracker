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


async def _generate_approved_reports_safe(payroll_run_id) -> None:
    from fw.core.db import async_session_factory
    from fw.modules.notifications import NotificationService

    async with async_session_factory() as session:
        try:
            await ReportService.generate_month_end_reports(
                session=session,
                payroll_run_id=payroll_run_id,
                is_approval=True,
                generated_by_user="system",
            )
            await session.commit()
            logger.info("month_end_reports_approved_completed", run_id=str(payroll_run_id))
        except Exception as e:
            await session.rollback()
            logger.error(
                "month_end_reports_approved_failed", error=str(e), run_id=str(payroll_run_id)
            )
            try:
                async with async_session_factory() as alert_session:
                    await NotificationService.create_alert(
                        session=alert_session,
                        alert_type="MONTH_END_REPORTS_FAILED",
                        title=f"Month-end report generation failed for run {payroll_run_id}",
                        message=f"Report generation error: {e}",
                        ref_type="PAYROLL_RUN",
                        ref_id=payroll_run_id,
                        target_role="ADMIN",
                    )
                    await alert_session.commit()
            except Exception as alert_err:
                logger.error("failed_to_create_month_end_reports_alert", error=str(alert_err))


async def handle_payroll_run_approved(event: PayrollRunApproved) -> None:
    """When a payroll run is approved, generate the final immutable month-end reports post-commit."""
    if not event.payroll_run_id:
        return

    logger.info("handling_payroll_run_approved_for_reports", run_id=str(event.payroll_run_id))
    await _generate_approved_reports_safe(event.payroll_run_id)


_registered = False


def register_reports_listeners() -> None:
    """Register reports event listeners with the domain event bus."""
    global _registered
    if not _registered:
        event_bus.subscribe_sync(PayrollRunCreated, handle_payroll_run_created)
        event_bus.subscribe_post_commit(PayrollRunApproved, handle_payroll_run_approved)
        _registered = True
