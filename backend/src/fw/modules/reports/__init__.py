"""Public interface for reports module."""

from fw.modules.reports.api import router as reports_router
from fw.modules.reports.listeners import register_reports_listeners
from fw.modules.reports.models import GeneratedReport, ReportExport
from fw.modules.reports.registry import (
    MONTH_END_REPORT_KEYS,
    can_access_report,
    get_report_definition,
    list_reports_for_role,
)
from fw.modules.reports.schemas import (
    GeneratedReportFilterParams,
    GeneratedReportRead,
    ReportColumn,
    ReportDataResponse,
    ReportDefinition,
    ReportExportRequest,
    ReportExportResponse,
    ReportFilterParams,
)
from fw.modules.reports.service import ReportService

__all__ = [
    "GeneratedReport",
    "GeneratedReportFilterParams",
    "GeneratedReportRead",
    "MONTH_END_REPORT_KEYS",
    "ReportColumn",
    "ReportDataResponse",
    "ReportDefinition",
    "ReportExport",
    "ReportExportRequest",
    "ReportExportResponse",
    "ReportFilterParams",
    "ReportService",
    "can_access_report",
    "get_report_definition",
    "list_reports_for_role",
    "register_reports_listeners",
    "reports_router",
]
