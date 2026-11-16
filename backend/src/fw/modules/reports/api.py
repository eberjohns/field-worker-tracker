"""FastAPI router for reports, background exports, and generated reports history."""

import io
from uuid import UUID

from fastapi import APIRouter, Depends, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from fw.core.db import get_db
from fw.modules.identity import User, get_current_user
from fw.modules.reports.registry import list_reports_for_role
from fw.modules.reports.schemas import (
    GeneratedReportFilterParams,
    GeneratedReportRead,
    ReportDataResponse,
    ReportDefinition,
    ReportExportRequest,
    ReportExportResponse,
    ReportFilterParams,
)
from fw.modules.reports.service import ReportService

router = APIRouter(tags=["reports"])


@router.get("/reports", response_model=list[ReportDefinition])
async def list_available_reports(
    current_user: User = Depends(get_current_user),
) -> list[ReportDefinition]:
    """List reports accessible to the calling user's role."""
    return list_reports_for_role(current_user.role)


@router.get("/reports/{key}", response_model=ReportDataResponse)
async def get_report_data(
    key: str,
    filters: ReportFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportDataResponse:
    """Run a report with filter parameters (paginated, scope applied)."""
    return await ReportService.get_report_data(
        session=session,
        report_key=key,
        filters=filters,
        current_user=current_user,
    )


@router.post(
    "/reports/{key}/export",
    response_model=ReportExportResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def request_report_export(
    key: str,
    payload: ReportExportRequest,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportExportResponse:
    """Trigger report export as a background job (supports xlsx, csv, pdf)."""
    return await ReportService.create_export_job(
        session=session,
        report_key=key,
        fmt=payload.format,
        params=payload.params,
        current_user=current_user,
    )


@router.get("/exports/{export_id}", response_model=ReportExportResponse)
async def get_export_status(
    export_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> ReportExportResponse:
    """Check status of a requested report export job."""
    return await ReportService.get_export_status(
        session=session,
        export_id=export_id,
        current_user=current_user,
    )


@router.get("/exports/{export_id}/download")
async def download_export_file(
    export_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Download the completed export file."""
    content, file_name, mime_type = await ReportService.download_export(
        session=session,
        export_id=export_id,
        current_user=current_user,
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )


@router.get("/generated-reports", response_model=list[GeneratedReportRead])
async def list_generated_reports(
    filters: GeneratedReportFilterParams = Depends(),
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
) -> list[GeneratedReportRead]:
    """List archived month-end and on-demand report history files."""
    return await ReportService.list_generated_reports(
        session=session,
        filters=filters,
        current_user=current_user,
    )


@router.get("/generated-reports/{report_id}/download")
async def download_generated_report(
    report_id: UUID,
    current_user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db),
):
    """Re-download an archived generated report file."""
    content, file_name, mime_type = await ReportService.download_generated_report(
        session=session,
        report_id=report_id,
        current_user=current_user,
    )
    return StreamingResponse(
        io.BytesIO(content),
        media_type=mime_type,
        headers={"Content-Disposition": f'attachment; filename="{file_name}"'},
    )
