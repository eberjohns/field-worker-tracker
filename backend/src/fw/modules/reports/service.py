"""Reports service handling query dispatch, background export jobs, and month-end report archiving."""

import re
from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from fw.adapters.storage import get_file_storage
from fw.core.errors import AppError
from fw.modules.identity.models import User
from fw.modules.notifications import NotificationService
from fw.modules.org.service import ScopeService
from fw.modules.payroll.models import PayrollRun
from fw.modules.reports.formatters.csv_formatter import generate_csv_report
from fw.modules.reports.formatters.excel import generate_excel_report
from fw.modules.reports.formatters.pdf_formatter import generate_pdf_report
from fw.modules.reports.handlers.daily_attendance import fetch_daily_attendance
from fw.modules.reports.handlers.document_expiry import fetch_document_expiry
from fw.modules.reports.handlers.employee_movement import fetch_employee_movement
from fw.modules.reports.handlers.employee_utilization import fetch_employee_utilization
from fw.modules.reports.handlers.job_costing import fetch_job_costing
from fw.modules.reports.handlers.late_early_departure import fetch_late_early_departure
from fw.modules.reports.handlers.monthly_attendance import fetch_monthly_attendance
from fw.modules.reports.handlers.payroll import fetch_payroll
from fw.modules.reports.handlers.pending_visits import fetch_pending_visits
from fw.modules.reports.handlers.project_attendance_summary import fetch_project_attendance_summary
from fw.modules.reports.handlers.provisions_staff_cost import fetch_provisions_staff_cost
from fw.modules.reports.handlers.site_visits import fetch_site_visits
from fw.modules.reports.handlers.staffing_gaps import fetch_staffing_gaps
from fw.modules.reports.handlers.transportation_time import fetch_transportation_time
from fw.modules.reports.handlers.weekly_roster import fetch_weekly_roster
from fw.modules.reports.models import GeneratedReport, ReportExport
from fw.modules.reports.registry import (
    MONTH_END_REPORT_KEYS,
    can_access_report,
    get_report_definition,
)
from fw.modules.reports.schemas import (
    GeneratedReportFilterParams,
    GeneratedReportRead,
    ReportDataResponse,
    ReportExportResponse,
    ReportFilterParams,
)
from fw.modules.settings.service import SettingsService

logger = structlog.get_logger(__name__)

# Map of report keys to handler query functions
HANDLERS = {
    "daily-attendance": fetch_daily_attendance,
    "monthly-attendance": fetch_monthly_attendance,
    "employee-movement": fetch_employee_movement,
    "site-visits": fetch_site_visits,
    "employee-utilization": fetch_employee_utilization,
    "transportation-time": fetch_transportation_time,
    "late-early-departure": fetch_late_early_departure,
    "project-attendance-summary": fetch_project_attendance_summary,
    "pending-visits": fetch_pending_visits,
    "staffing-gaps": fetch_staffing_gaps,
    "document-expiry": fetch_document_expiry,
    "weekly-roster": fetch_weekly_roster,
    "payroll": fetch_payroll,
    "provisions-staff-cost": fetch_provisions_staff_cost,
    "job-costing": fetch_job_costing,
}


class ReportService:
    """Service orchestrating report executions, exports, and history snapshots."""

    @staticmethod
    async def get_report_data(
        session: AsyncSession,
        report_key: str,
        filters: ReportFilterParams,
        current_user: User,
    ) -> ReportDataResponse:
        """Execute report query with role validation and reporting scope enforcement."""
        # 1. Role permission gate
        if not can_access_report(report_key, current_user.role):
            raise AppError(
                code="FORBIDDEN",
                message=f"Access denied for report: {report_key}",
                status_code=403,
            )

        spec = get_report_definition(report_key)
        handler = HANDLERS.get(report_key)
        if not handler:
            raise AppError(
                code="NOT_FOUND",
                message=f"No query handler for report: {report_key}",
                status_code=404,
            )

        # 2. Scope resolution
        scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)

        # 3. Handler execution
        all_rows = await handler(session=session, filters=filters, scoped_ids=scoped_ids)

        total_rows = len(all_rows)
        # 4. Pagination
        start_idx = (filters.page - 1) * filters.page_size
        end_idx = start_idx + filters.page_size
        paginated_rows = all_rows[start_idx:end_idx]

        return ReportDataResponse(
            report_key=report_key,
            total_rows=total_rows,
            page=filters.page,
            page_size=filters.page_size,
            columns=spec.columns,
            data=paginated_rows,
            summary={"total_records": total_rows},
        )

    @staticmethod
    async def create_export_job(
        session: AsyncSession,
        report_key: str,
        fmt: str,
        params: dict[str, Any],
        current_user: User,
    ) -> ReportExportResponse:
        """Create and immediately execute or queue a report export job."""
        if not can_access_report(report_key, current_user.role):
            raise AppError(
                code="FORBIDDEN",
                message=f"Access denied for report: {report_key}",
                status_code=403,
            )

        spec = get_report_definition(report_key)
        if fmt not in spec.supported_formats:
            raise AppError(
                code="BAD_REQUEST",
                message=f"Format {fmt} is not supported for {report_key}. Supported: {spec.supported_formats}",
                status_code=400,
            )

        export = ReportExport(
            report_key=report_key,
            format=fmt,
            status="PENDING",
            params=params,
            requested_by_user_id=current_user.id,
        )
        session.add(export)
        await session.flush()

        # Execute export
        try:
            filter_obj = ReportFilterParams(**params)
            scoped_ids = await ScopeService.get_scoped_employee_ids(session, current_user)
            handler = HANDLERS[report_key]
            rows = await handler(session=session, filters=filter_obj, scoped_ids=scoped_ids)

            # Generate format content
            ts_str = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
            safe_name = spec.name.replace(" ", "-")
            file_name = f"{safe_name}_{ts_str}.{fmt}"

            if fmt == "xlsx":
                content = generate_excel_report(spec.columns, rows, params, title=spec.name)
            elif fmt == "csv":
                content = generate_csv_report(spec.columns, rows)
            elif fmt == "pdf":
                content = generate_pdf_report(spec.columns, rows, title=spec.name, filters=params)
            else:
                raise ValueError(f"Unsupported format: {fmt}")

            # Store file
            storage = get_file_storage()
            rel_path = f"exports/{export.id}/{file_name}"
            file_ref, size_bytes, sha256_hash = await storage.save(rel_path, content)

            export.status = "COMPLETED"
            export.file_name = file_name
            export.file_ref = file_ref
            export.file_size_bytes = size_bytes
            export.file_hash = sha256_hash
            export.completed_at = datetime.now(UTC)
            await session.commit()

            return ReportExportResponse(
                id=export.id,
                report_key=export.report_key,
                format=export.format,
                status=export.status,
                download_url=f"/exports/{export.id}/download",
                file_name=export.file_name,
                file_size_bytes=export.file_size_bytes,
                created_at=export.created_at,
                completed_at=export.completed_at,
            )
        except Exception as e:
            logger.exception("report_export_failed", export_id=export.id, error=str(e))
            export.status = "FAILED"
            export.error_message = str(e)
            await session.commit()
            raise

    @staticmethod
    async def get_export_status(
        session: AsyncSession,
        export_id: UUID,
        current_user: User,
    ) -> ReportExportResponse:
        """Get status of an export job."""
        export = await session.get(ReportExport, export_id)
        if not export:
            raise AppError(code="NOT_FOUND", message="Export not found", status_code=404)

        if current_user.role != "ADMIN" and export.requested_by_user_id != current_user.id:
            raise AppError(code="FORBIDDEN", message="Access denied", status_code=403)

        dl_url = f"/api/v1/exports/{export.id}/download" if export.status == "COMPLETED" else None
        return ReportExportResponse(
            id=export.id,
            report_key=export.report_key,
            format=export.format,
            status=export.status,
            download_url=dl_url,
            file_name=export.file_name,
            file_size_bytes=export.file_size_bytes,
            created_at=export.created_at,
            completed_at=export.completed_at,
        )

    @staticmethod
    async def download_export(
        session: AsyncSession,
        export_id: UUID,
        current_user: User,
    ) -> tuple[bytes, str, str]:
        """Download binary content of a completed export."""
        export = await session.get(ReportExport, export_id)
        if not export or export.status != "COMPLETED" or not export.file_ref:
            raise AppError(code="NOT_FOUND", message="Export file not available", status_code=404)

        if current_user.role != "ADMIN" and export.requested_by_user_id != current_user.id:
            raise AppError(code="FORBIDDEN", message="Access denied", status_code=403)

        content = await get_file_storage().read(export.file_ref)
        mime = (
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            if export.format == "xlsx"
            else ("text/csv" if export.format == "csv" else "application/pdf")
        )
        return content, export.file_name or f"export.{export.format}", mime

    @staticmethod
    async def generate_month_end_reports(
        session: AsyncSession,
        payroll_run_id: UUID,
        is_approval: bool = False,
        generated_by_user: str = "system",
    ) -> list[GeneratedReport]:
        """Automatically generate and archive the 11 month-end reports for a payroll run (DEC-45, DEC-46)."""
        run = await session.get(PayrollRun, payroll_run_id)
        if not run:
            raise AppError(code="NOT_FOUND", message="Payroll run not found", status_code=404)

        # Company name
        raw_company = await SettingsService.get_setting(
            session=session,
            key="company_name",
            country=run.country,
            default="FieldWorkerTracker",
        )
        company_clean = re.sub(r"[^A-Za-z0-9]", "", str(raw_company or "FieldWorkerTracker"))
        period_str = run.period_start.strftime("%Y-%m")
        country = run.country or "AE"
        version_no = run.run_no
        status_tag = "APPROVED" if is_approval else "DRAFT"

        # Timestamp for file name
        now_dt = datetime.now(UTC)
        ts_str = now_dt.strftime("%Y%m%d-%H%M%S")

        created_reports: list[GeneratedReport] = []
        storage = get_file_storage()

        for key in MONTH_END_REPORT_KEYS:
            spec = get_report_definition(key)
            handler = HANDLERS[key]

            # Run query for the month
            filter_params = ReportFilterParams(
                country=country,
                date_from=run.period_start,
                date_to=run.period_end,
                payroll_run_id=run.id,
                year=run.period_start.year,
                month=run.period_start.month,
            )
            rows = await handler(session=session, filters=filter_params, scoped_ids=None)

            # Name: <Company>_<Report>_<Country>_<Period>_generated-<datetime>.xlsx
            report_title_slug = spec.name.replace(" ", "-")
            file_name = f"{company_clean}_{report_title_slug}_{country}_{period_str}_generated-{ts_str}.xlsx"
            if is_approval:
                file_name = f"{company_clean}_{report_title_slug}_{country}_{period_str}_APPROVED_generated-{ts_str}.xlsx"

            applied_filters = {
                "period": period_str,
                "country": country,
                "payroll_run_id": str(run.id),
                "run_no": run.run_no,
                "status": status_tag,
            }

            xlsx_bytes = generate_excel_report(spec.columns, rows, applied_filters, title=spec.name)

            rel_path = f"reports/{country}/{period_str}/{file_name}"
            file_ref, size_bytes, sha256_hash = await storage.save(rel_path, xlsx_bytes)

            visible_roles = (
                ["ADMIN"]
                if spec.is_cost_report
                else ["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"]
            )

            gen_rep = GeneratedReport(
                report_key=key,
                country=country,
                period_start=run.period_start,
                period_end=run.period_end,
                kind="MONTH_END",
                params=applied_filters,
                file_name=file_name,
                file_ref=file_ref,
                file_size_bytes=size_bytes,
                file_hash=sha256_hash,
                payroll_run_id=run.id,
                version_no=version_no,
                status=status_tag,
                visible_roles=visible_roles,
                generated_by=generated_by_user,
                generated_at=now_dt,
            )
            session.add(gen_rep)
            created_reports.append(gen_rep)

        await session.flush()

        # Send in-app notification to Admin (and Engineers)
        notif_title = (
            f"Final Approved Month-End Reports Ready ({period_str} - {country})"
            if is_approval
            else f"Month-End Draft Reports Ready ({period_str} - {country})"
        )
        notif_msg = f"Payroll run #{run.run_no} reports have been generated and archived in Generated Reports."

        try:
            await NotificationService.create_alert(
                session=session,
                alert_type="MONTH_END_REPORTS_READY",
                title=notif_title,
                message=notif_msg,
                ref_type="payroll_run",
                ref_id=run.id,
                target_role="ADMIN",
                details={"period": period_str, "country": country, "is_approval": is_approval},
            )
        except Exception as e:
            logger.warning("notification_dispatch_failed", error=str(e))

        logger.info(
            "month_end_reports_generated",
            payroll_run_id=str(run.id),
            count=len(created_reports),
            period=period_str,
            is_approval=is_approval,
        )
        return created_reports

    @staticmethod
    async def list_generated_reports(
        session: AsyncSession,
        filters: GeneratedReportFilterParams,
        current_user: User,
    ) -> list[GeneratedReportRead]:
        """List generated reports history filtered by role visibility and search criteria."""
        stmt = select(GeneratedReport).order_by(
            GeneratedReport.generated_at.desc(), GeneratedReport.file_name.asc()
        )

        conditions = []
        if filters.report_key:
            conditions.append(GeneratedReport.report_key == filters.report_key)
        if filters.country:
            conditions.append(GeneratedReport.country == filters.country)
        if filters.kind:
            conditions.append(GeneratedReport.kind == filters.kind)
        if filters.status:
            conditions.append(GeneratedReport.status == filters.status)
        if filters.period:
            # Parse YYYY-MM
            try:
                parts = filters.period.split("-")
                yr, mo = int(parts[0]), int(parts[1])
                import calendar

                _, l_day = calendar.monthrange(yr, mo)
                p_st = date(yr, mo, 1)
                p_en = date(yr, mo, l_day)
                conditions.append(
                    and_(
                        GeneratedReport.period_start == p_st,
                        GeneratedReport.period_end == p_en,
                    )
                )
            except Exception:
                pass

        if conditions:
            stmt = stmt.where(and_(*conditions))

        result = await session.execute(stmt)
        reports = result.scalars().all()

        user_role = current_user.role.upper()
        items: list[GeneratedReportRead] = []
        for r in reports:
            # Check visibility
            roles = [str(x).upper() for x in (r.visible_roles or [])]
            if user_role not in roles and user_role != "ADMIN":
                continue

            items.append(
                GeneratedReportRead(
                    id=r.id,
                    report_key=r.report_key,
                    country=r.country,
                    period_start=r.period_start,
                    period_end=r.period_end,
                    kind=r.kind,
                    file_name=r.file_name,
                    version_no=r.version_no,
                    status=r.status,
                    visible_roles=r.visible_roles,
                    generated_by=r.generated_by,
                    generated_at=r.generated_at,
                    file_size_bytes=r.file_size_bytes,
                    download_url=f"/api/v1/generated-reports/{r.id}/download",
                )
            )

        return items

    @staticmethod
    async def download_generated_report(
        session: AsyncSession,
        report_id: UUID,
        current_user: User,
    ) -> tuple[bytes, str, str]:
        """Download archived report file with role visibility enforcement."""
        r = await session.get(GeneratedReport, report_id)
        if not r:
            raise AppError(code="NOT_FOUND", message="Generated report not found", status_code=404)

        user_role = current_user.role.upper()
        roles = [str(x).upper() for x in (r.visible_roles or [])]
        if user_role not in roles and user_role != "ADMIN":
            raise AppError(
                code="FORBIDDEN",
                message="You do not have permission to view this generated report.",
                status_code=403,
            )

        storage = get_file_storage()
        content = await storage.read(r.file_ref)
        mime = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        return content, r.file_name, mime
