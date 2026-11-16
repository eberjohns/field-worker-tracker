/**
 * API client for Reports and Generated Reports history (Phase 12).
 */

export interface ReportColumn {
  key: string;
  label: string;
  type: "string" | "number" | "currency" | "date" | "time" | "percentage" | "badge";
  width?: number;
}

export interface ReportMetadata {
  key: string;
  name: string;
  description: string;
  category: "operations" | "attendance" | "payroll" | "compliance" | "planning";
  supported_formats: ("xlsx" | "csv" | "pdf")[];
  allowed_roles: string[];
  columns: ReportColumn[];
  filter_schema: Record<string, unknown>;
}

export interface ReportFilterParams {
  date_from?: string;
  date_to?: string;
  year?: number;
  month?: number;
  country?: string;
  worksite_id?: string;
  supervisor_id?: string;
  employee_id?: string;
  payroll_run_id?: string;
  days_ahead?: number;
  include_cost?: boolean;
}

export interface ReportDataResponse {
  report_key: string;
  generated_at: string;
  filters_applied: Record<string, unknown>;
  total_rows: number;
  columns: ReportColumn[];
  data: Record<string, unknown>[];
}

export interface ReportExportResponse {
  id: string;
  report_key: string;
  format: "xlsx" | "csv" | "pdf";
  status: "PENDING" | "PROCESSING" | "COMPLETED" | "FAILED";
  download_url?: string | null;
  file_name?: string | null;
  file_size_bytes?: number | null;
  error_message?: string | null;
  created_at: string;
  completed_at?: string | null;
}

export interface GeneratedReportItem {
  id: string;
  report_key: string;
  country: string;
  period_start: string;
  period_end: string;
  kind: "MONTH_END" | "ON_DEMAND";
  file_name: string;
  version_no: number;
  status: "DRAFT" | "APPROVED";
  visible_roles: string[];
  generated_by: string;
  generated_at: string;
  file_size_bytes?: number | null;
  download_url: string;
}

export interface GeneratedReportFilters {
  report_key?: string;
  country?: string;
  period?: string;
  kind?: string;
  status?: string;
}

function getAuthHeaders(token?: string | null): Record<string, string> {
  const headers: Record<string, string> = {};
  const effectiveToken = token || localStorage.getItem("fwt_token");
  if (effectiveToken) {
    headers["Authorization"] = `Bearer ${effectiveToken}`;
  }
  return headers;
}

export async function fetchReportsRegistry(token?: string | null): Promise<ReportMetadata[]> {
  const res = await fetch("/api/v1/reports", {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch reports catalog");
  }
  return res.json();
}

export async function fetchReportData(
  key: string,
  filters: ReportFilterParams,
  token?: string | null
): Promise<ReportDataResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  });

  const res = await fetch(`/api/v1/reports/${encodeURIComponent(key)}?${params.toString()}`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Failed to fetch report: ${key}`);
  }
  return res.json();
}

export async function triggerExportJob(
  key: string,
  filters: ReportFilterParams,
  format: "xlsx" | "csv" | "pdf",
  token?: string | null
): Promise<ReportExportResponse> {
  const params = new URLSearchParams();
  params.set("format", format);
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  });

  const res = await fetch(`/api/v1/reports/${encodeURIComponent(key)}/export?${params.toString()}`, {
    method: "POST",
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `Export request failed for ${key}`);
  }
  return res.json();
}

export async function getExportStatus(
  exportId: string,
  token?: string | null
): Promise<ReportExportResponse> {
  const res = await fetch(`/api/v1/exports/${exportId}`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to check export status");
  }
  return res.json();
}

export async function downloadFile(
  downloadUrl: string,
  defaultFilename: string,
  token?: string | null
): Promise<void> {
  const res = await fetch(downloadUrl, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    throw new Error(`Failed to download file (HTTP ${res.status})`);
  }

  // Get filename from header or fallback
  const disposition = res.headers.get("Content-Disposition");
  let filename = defaultFilename;
  if (disposition && disposition.includes("filename=")) {
    const match = disposition.match(/filename="?([^"]+)"?/);
    if (match && match[1]) {
      filename = match[1];
    }
  }

  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  window.URL.revokeObjectURL(url);
  document.body.removeChild(a);
}

export async function fetchGeneratedReports(
  filters: GeneratedReportFilters = {},
  token?: string | null
): Promise<GeneratedReportItem[]> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([k, v]) => {
    if (v !== undefined && v !== null && v !== "") {
      params.set(k, String(v));
    }
  });

  const res = await fetch(`/api/v1/generated-reports?${params.toString()}`, {
    headers: getAuthHeaders(token),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || "Failed to fetch generated reports history");
  }
  return res.json();
}

