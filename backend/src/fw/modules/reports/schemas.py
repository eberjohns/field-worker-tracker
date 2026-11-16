"""Pydantic schemas for reports, exports, and generated reports history."""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class ReportFilterParams(BaseModel):
    """Common filter parameters accepted across reports."""

    model_config = ConfigDict(extra="ignore")

    date_from: date | None = None
    date_to: date | None = None
    worksite_id: UUID | None = None
    group_id: UUID | None = None
    zone_id: UUID | None = None
    supervisor_id: UUID | None = None
    superintendent_id: UUID | None = None
    engineer_id: UUID | None = None
    employee_id: UUID | None = None
    sgd: str | None = None
    country: str | None = "AE"
    month: int | None = None
    year: int | None = None
    week_start: date | None = None
    payroll_run_id: UUID | None = None
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=50, ge=1, le=1000)


class ReportColumn(BaseModel):
    """Metadata for a report column."""

    key: str
    label: str
    type: str = "string"  # string, number, date, datetime, duration, money, badge
    description: str | None = None


class ReportDefinition(BaseModel):
    """Specification of an available report."""

    key: str
    name: str
    description: str
    category: str  # Operational, Salary & Cost, Compliance
    allowed_roles: list[str]
    is_cost_report: bool
    columns: list[ReportColumn]
    supported_formats: list[str]


class ReportDataResponse(BaseModel):
    """Paginated report results."""

    report_key: str
    total_rows: int
    page: int
    page_size: int
    columns: list[ReportColumn]
    data: list[dict[str, Any]]
    summary: dict[str, Any] = Field(default_factory=dict)


class ReportExportRequest(BaseModel):
    """Export request body."""

    format: str = Field(default="xlsx", pattern="^(xlsx|csv|pdf)$")
    params: dict[str, Any] = Field(default_factory=dict)


class ReportExportResponse(BaseModel):
    """Export job status response."""

    id: UUID
    report_key: str
    format: str
    status: str
    download_url: str | None = None
    file_name: str | None = None
    file_size_bytes: int | None = None
    created_at: datetime
    completed_at: datetime | None = None


class GeneratedReportRead(BaseModel):
    """Archived generated report item."""

    id: UUID
    report_key: str
    country: str
    period_start: date | None = None
    period_end: date | None = None
    kind: str
    file_name: str
    version_no: int
    status: str
    visible_roles: list[str]
    generated_by: str
    generated_at: datetime
    file_size_bytes: int | None = None
    download_url: str


class GeneratedReportFilterParams(BaseModel):
    """Filters for listing generated reports history."""

    report_key: str | None = None
    country: str | None = None
    period: str | None = None  # e.g. "2026-10"
    kind: str | None = None  # MONTH_END | ON_DEMAND
    status: str | None = None  # DRAFT | APPROVED
