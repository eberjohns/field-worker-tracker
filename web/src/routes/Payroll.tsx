import React, { useState, useEffect } from "react";
import {
  DollarSign,
  Calendar,
  AlertTriangle,
  CheckCircle2,
  Lock,
  RefreshCw,
  FileText,
  TrendingUp,
  TrendingDown,
  Info,
  Download,
  Upload,
  ArrowRight,
  Search,
  Check,
  X,
  Layers,
  ChevronDown,
  ChevronRight,
  Building,
  AlertCircle,
} from "lucide-react";
import { useAuth } from "../context/AuthContext";

// --- Types ---

interface PayrollRunItem {
  id: string;
  country: string;
  period_start: string;
  period_end: string;
  run_no: number;
  status: "DRAFT" | "APPROVED";
  created_at: string;
  approved_at: string | null;
  approved_by_user_id: string | null;
  notes: string | null;
  record_count: number;
  total_gross_pay: number;
  total_net_pay: number;
  total_employer_cost: number;
}

interface PayrollRecordItem {
  id: string;
  employee_id: string;
  employee_tally_id: string;
  employee_name: string;
  employee_role: string;
  standard_monthly_hours: number;
  actual_worked_hours: number;
  leave_hours: number;
  missed_hours: number;
  missed_hours_deduction: number;
  salary_portion: number;
  basic_salary: number;
  special_allowance: number;
  fixed_ot_amount: number;
  bonus: number;
  ot1_hours: number;
  ot1_rate: number;
  ot1_amount: number;
  ot2_hours: number;
  ot2_rate: number;
  ot2_amount: number;
  gross_pay: number;
  total_deductions: number;
  net_pay: number;
  gratuity_provision: number;
  leave_salary_provision: number;
  company_provisions_total: number;
  hr_overhead_amount: number;
  final_total_staff_cost: number;
  snapshot: any;
}

interface RunIssuesData {
  payroll_run_id: string;
  status: string;
  unapproved_overtime_count: number;
  missing_salary_structure_count: number;
  issues: Array<{
    issue_type: "UNAPPROVED_OVERTIME" | "MISSING_SALARY_STRUCTURE";
    employee_id: string;
    employee_name: string;
    tally_id: string;
    work_date?: string;
    description: string;
    suggested_action: string;
  }>;
}

interface RevisionLineItem {
  grade_code: string;
  grade_group_title?: string;
  basic_salary: number;
  special_allowance: number;
  fixed_ot_amount: number;
  bonus: number;
  visa_provision: number;
  air_ticket_provision: number;
  uniform_provision: number;
  medical_provision: number;
  accommodation_provision: number;
  planned_hourly_cost: number;
}

interface RevisionSummary {
  id: string;
  code: string;
  name: string;
  country: string;
  effective_from: string;
  lines_count: number;
}

interface BudgetVsActualItem {
  worksite_id: string;
  job_number: string;
  job_name: string;
  country: string;
  assigned_revision_code: string | null;
  annual_planned_man_hours: number;
  annual_labor_budget: number;
  pro_rated_budget: number;
  actual_allocated_cost: number;
  variance_amount: number;
  variance_percent: number;
  is_under_budget: boolean;
  is_custom_budget_override: boolean;
}

export const Payroll: React.FC = () => {
  const { token, user } = useAuth();
  const isAdmin = user?.role === "ADMIN";
  const isEngineer = user?.role === "ENGINEER";
  const canAccess = isAdmin || isEngineer;

  // Active Tab
  const [activeTab, setActiveTab] = useState<"RUNS" | "REVISIONS" | "BUDGET">("RUNS");

  // Tab 1: Runs state
  const [runs, setRuns] = useState<PayrollRunItem[]>([]);
  const [selectedRunId, setSelectedRunId] = useState<string | null>(null);
  const [selectedRunDetail, setSelectedRunDetail] = useState<{
    run: PayrollRunItem;
    records: PayrollRecordItem[];
  } | null>(null);
  const [runIssues, setRunIssues] = useState<RunIssuesData | null>(null);
  const [issuesOpen, setIssuesOpen] = useState(false);
  const [runsLoading, setRunsLoading] = useState(false);
  const [recordSearch, setRecordSearch] = useState("");
  const [selectedRecord, setSelectedRecord] = useState<PayrollRecordItem | null>(null);
  const [formulaModalOpen, setFormulaModalOpen] = useState(false);

  // Draft generation modal
  const [generateModalOpen, setGenerateModalOpen] = useState(false);
  const [genPeriodStart, setGenPeriodStart] = useState("");
  const [genPeriodEnd, setGenPeriodEnd] = useState("");
  const [genCountry, setGenCountry] = useState("AE");
  const [genNotes, setGenNotes] = useState("");
  const [generating, setGenerating] = useState(false);

  // Approve modal
  const [approveModalOpen, setApproveModalOpen] = useState(false);
  const [approveNotes, setApproveNotes] = useState("");
  const [approving, setApproving] = useState(false);

  // Tab 2: Salary Revisions state
  const [revisions, setRevisions] = useState<RevisionSummary[]>([]);
  const [selectedRevisionCode, setSelectedRevisionCode] = useState<string>("");
  const [activeRevisionLines, setActiveRevisionLines] = useState<RevisionLineItem[]>([]);
  const [revisionsLoading, setRevisionsLoading] = useState(false);
  const [diffModalOpen, setDiffModalOpen] = useState(false);
  const [targetRevisionInput, setTargetRevisionInput] = useState("");
  const [diffInputJson, setDiffInputJson] = useState("");
  const [diffResult, setDiffResult] = useState<any | null>(null);
  const [diffLoading, setDiffLoading] = useState(false);

  // Tab 3: Budget vs Actual state
  const [budgetItems, setBudgetItems] = useState<BudgetVsActualItem[]>([]);
  const [budgetLoading, setBudgetLoading] = useState(false);
  const [countryBudgetFilter, setCountryBudgetFilter] = useState("AE");
  const [updatingWorksiteRevId, setUpdatingWorksiteRevId] = useState<string | null>(null);

  // --- Fetch Runs ---
  const fetchRuns = async () => {
    if (!token) return;
    setRunsLoading(true);
    try {
      const res = await fetch("/api/v1/payroll/runs", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRuns(data);
        if (data.length > 0 && !selectedRunId) {
          setSelectedRunId(data[0].id);
        }
      }
    } catch (err) {
      console.error("Failed to load payroll runs", err);
    } finally {
      setRunsLoading(false);
    }
  };

  // --- Fetch Run Detail & Issues ---
  const fetchRunDetail = async (runId: string) => {
    if (!token) return;
    try {
      const [detRes, issRes] = await Promise.all([
        fetch(`/api/v1/payroll/runs/${runId}`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
        fetch(`/api/v1/payroll/runs/${runId}/issues`, {
          headers: { Authorization: `Bearer ${token}` },
        }),
      ]);
      if (detRes.ok) {
        const detData = await detRes.json();
        setSelectedRunDetail({
          run: detData,
          records: detData.records || [],
        });
      }
      if (issRes.ok) {
        const issData = await issRes.json();
        setRunIssues(issData);
      }
    } catch (err) {
      console.error("Failed to load run detail", err);
    }
  };

  // --- Fetch Revisions ---
  const fetchRevisions = async () => {
    if (!token) return;
    setRevisionsLoading(true);
    try {
      const res = await fetch("/api/v1/salary-revisions", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data: RevisionSummary[] = await res.json();
        setRevisions(data);
        if (data.length > 0 && !selectedRevisionCode) {
          setSelectedRevisionCode(data[0].code);
        }
      }
    } catch (err) {
      console.error("Failed to load salary revisions", err);
    } finally {
      setRevisionsLoading(false);
    }
  };

  const fetchRevisionDetail = async (code: string) => {
    if (!token || !code) return;
    try {
      const res = await fetch(`/api/v1/salary-revisions/${encodeURIComponent(code)}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setActiveRevisionLines(data.lines || []);
      }
    } catch (err) {
      console.error("Failed to load revision detail", err);
    }
  };

  // --- Fetch Budget vs Actual ---
  const fetchBudgetVsActual = async () => {
    if (!token) return;
    setBudgetLoading(true);
    try {
      const url = countryBudgetFilter
        ? `/api/v1/payroll/budget-vs-actual?country=${countryBudgetFilter}`
        : "/api/v1/payroll/budget-vs-actual";
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setBudgetItems(data);
      }
    } catch (err) {
      console.error("Failed to load budget vs actual", err);
    } finally {
      setBudgetLoading(false);
    }
  };

  // Initial loads
  useEffect(() => {
    if (canAccess) {
      fetchRuns();
      fetchRevisions();
      fetchBudgetVsActual();
    }
  }, [token, canAccess]);

  useEffect(() => {
    if (selectedRunId) {
      fetchRunDetail(selectedRunId);
    }
  }, [selectedRunId, token]);

  useEffect(() => {
    if (selectedRevisionCode) {
      fetchRevisionDetail(selectedRevisionCode);
    }
  }, [selectedRevisionCode, token]);

  useEffect(() => {
    if (activeTab === "BUDGET") {
      fetchBudgetVsActual();
    }
  }, [activeTab, countryBudgetFilter]);

  // Actions
  const handleGenerateDraft = async () => {
    if (!genPeriodStart || !genPeriodEnd) return;
    setGenerating(true);
    try {
      const res = await fetch("/api/v1/payroll/runs", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          period_start: genPeriodStart,
          period_end: genPeriodEnd,
          country: genCountry,
          notes: genNotes.trim() || undefined,
        }),
      });
      if (res.ok) {
        const newRun = await res.json();
        setGenerateModalOpen(false);
        setGenNotes("");
        await fetchRuns();
        setSelectedRunId(newRun.id);
      } else {
        const errData = await res.json();
        alert(errData.detail || "Failed to generate payroll draft.");
      }
    } catch (err) {
      console.error("Failed to generate draft", err);
      alert("Error generating draft run.");
    } finally {
      setGenerating(false);
    }
  };

  const handleRerunDraft = async () => {
    if (!selectedRunDetail || !isAdmin) return;
    if (!confirm(`Re-run draft for ${selectedRunDetail.run.period_start} to ${selectedRunDetail.run.period_end}? This will increment Run No and recalculate with latest approved attendance.`)) {
      return;
    }
    setRunsLoading(true);
    try {
      const res = await fetch("/api/v1/payroll/runs", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          period_start: selectedRunDetail.run.period_start,
          period_end: selectedRunDetail.run.period_end,
          country: selectedRunDetail.run.country,
          notes: `Re-run from Run #${selectedRunDetail.run.run_no}`,
        }),
      });
      if (res.ok) {
        const newRun = await res.json();
        await fetchRuns();
        setSelectedRunId(newRun.id);
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to re-run draft.");
      }
    } catch (err) {
      console.error("Failed to re-run draft", err);
    } finally {
      setRunsLoading(false);
    }
  };

  const handleApproveRun = async () => {
    if (!selectedRunId || !isAdmin) return;
    setApproving(true);
    try {
      const res = await fetch(`/api/v1/payroll/runs/${selectedRunId}/approve?notes=${encodeURIComponent(approveNotes)}`, {
        method: "POST",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        setApproveModalOpen(false);
        setApproveNotes("");
        await fetchRuns();
        await fetchRunDetail(selectedRunId);
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to approve payroll run.");
      }
    } catch (err) {
      console.error("Approve error", err);
    } finally {
      setApproving(false);
    }
  };

  const handleUpdateWorksiteRevision = async (worksiteId: string, revisionCode: string) => {
    setUpdatingWorksiteRevId(worksiteId);
    try {
      const res = await fetch(
        `/api/v1/payroll/worksites/${worksiteId}/revision?revision_code=${encodeURIComponent(revisionCode)}`,
        {
          method: "PUT",
          headers: { Authorization: `Bearer ${token}` },
        }
      );
      if (res.ok) {
        await fetchBudgetVsActual();
      } else {
        alert("Failed to update worksite revision.");
      }
    } catch (err) {
      console.error("Error updating worksite revision", err);
    } finally {
      setUpdatingWorksiteRevId(null);
    }
  };

  const handleExportRevisionTemplate = () => {
    const headers = [
      "grade_code",
      "grade_group_title",
      "basic_salary",
      "special_allowance",
      "fixed_ot_amount",
      "bonus",
      "visa_provision",
      "air_ticket_provision",
      "uniform_provision",
      "medical_provision",
      "accommodation_provision",
    ];
    const rows = activeRevisionLines.map((l) => [
      l.grade_code,
      l.grade_group_title || "",
      l.basic_salary,
      l.special_allowance,
      l.fixed_ot_amount,
      l.bonus,
      l.visa_provision,
      l.air_ticket_provision,
      l.uniform_provision,
      l.medical_provision,
      l.accommodation_provision,
    ]);
    const csvContent =
      "data:text/csv;charset=utf-8," +
      [headers.join(","), ...rows.map((e) => e.join(","))].join("\n");
    const encodedUri = encodeURI(csvContent);
    const link = document.createElement("a");
    link.setAttribute("href", encodedUri);
    link.setAttribute("download", `salary_revision_template_${selectedRevisionCode || "export"}.csv`);
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
  };

  const handleRunDiffPreview = async () => {
    if (!targetRevisionInput.trim()) {
      alert("Please enter a Target Revision Code.");
      return;
    }
    setDiffLoading(true);
    try {
      let lines = [];
      try {
        lines = JSON.parse(diffInputJson);
      } catch {
        alert("Invalid JSON format for lines. Please provide an array of grade objects.");
        setDiffLoading(false);
        return;
      }
      const res = await fetch(
        `/api/v1/salary-revisions/diff?target_revision_code=${encodeURIComponent(
          targetRevisionInput
        )}&base_revision_code=${encodeURIComponent(selectedRevisionCode)}`,
        {
          method: "POST",
          headers: {
            Authorization: `Bearer ${token}`,
            "Content-Type": "application/json",
          },
          body: JSON.stringify(lines),
        }
      );
      if (res.ok) {
        const data = await res.json();
        setDiffResult(data);
      } else {
        const err = await res.json();
        alert(err.detail || "Diff comparison failed.");
      }
    } catch (err) {
      console.error("Diff preview error", err);
    } finally {
      setDiffLoading(false);
    }
  };

  const handleSaveImportedRevision = async () => {
    if (!targetRevisionInput.trim() || !diffResult) return;
    setDiffLoading(true);
    try {
      const lines = JSON.parse(diffInputJson);
      const res = await fetch("/api/v1/salary-revisions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${token}`,
          "Content-Type": "application/json",
        },
        body: JSON.stringify({
          code: targetRevisionInput.trim(),
          name: `Salary Revision ${targetRevisionInput.trim()}`,
          country: "AE",
          effective_from: new Date().toISOString().split("T")[0],
          lines: lines,
        }),
      });
      if (res.ok) {
        setDiffModalOpen(false);
        setDiffResult(null);
        setDiffInputJson("");
        setTargetRevisionInput("");
        await fetchRevisions();
        setSelectedRevisionCode(targetRevisionInput.trim());
      } else {
        const err = await res.json();
        alert(err.detail || "Failed to save salary revision.");
      }
    } catch (err) {
      console.error("Save revision error", err);
    } finally {
      setDiffLoading(false);
    }
  };

  // Filter records
  const filteredRecords = (selectedRunDetail?.records || []).filter((r) => {
    if (!recordSearch.trim()) return true;
    const term = recordSearch.toLowerCase();
    return (
      r.employee_name.toLowerCase().includes(term) ||
      r.employee_tally_id.toLowerCase().includes(term) ||
      r.employee_role.toLowerCase().includes(term)
    );
  });

  if (!canAccess) {
    return (
      <div className="p-8 text-center bg-white rounded-xl border border-slate-200 space-y-4">
        <AlertCircle className="w-12 h-12 text-rose-500 mx-auto" />
        <h3 className="text-lg font-bold text-slate-800">Access Restricted</h3>
        <p className="text-slate-500 text-sm">
          Month-end payroll calculations and cost allocations are only accessible by Administrators and Engineers.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4 bg-white p-6 rounded-2xl border border-slate-200 shadow-xs">
        <div>
          <div className="flex items-center gap-3">
            <div className="p-2.5 bg-indigo-50 text-indigo-600 rounded-xl">
              <DollarSign className="w-6 h-6" />
            </div>
            <div>
              <h1 className="text-xl font-bold text-slate-900">Month-End Payroll & Job Budget</h1>
              <p className="text-xs text-slate-500">
                Monthly draft runs, unapproved overtime detection, immutable snapshots, grade revisions, and dynamic budget vs actual costs.
              </p>
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          {isAdmin && (
            <button
              onClick={() => {
                const now = new Date();
                const prevMonth = new Date(now.getFullYear(), now.getMonth() - 1, 1);
                const lastDay = new Date(now.getFullYear(), now.getMonth(), 0);
                setGenPeriodStart(prevMonth.toISOString().split("T")[0]);
                setGenPeriodEnd(lastDay.toISOString().split("T")[0]);
                setGenerateModalOpen(true);
              }}
              className="inline-flex items-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-semibold hover:bg-indigo-700 shadow-xs transition"
            >
              <Calendar className="w-4 h-4" />
              Generate Draft Run
            </button>
          )}

          <button
            onClick={() => setFormulaModalOpen(true)}
            className="inline-flex items-center gap-1.5 px-3 py-2 bg-slate-100 text-slate-700 rounded-xl text-xs font-medium hover:bg-slate-200 transition"
            title="Formula & Compliance Information"
          >
            <Info className="w-4 h-4 text-indigo-600" />
            <span>Formula Guide</span>
          </button>
        </div>
      </div>

      {/* Tabs Navigation */}
      <div className="flex border-b border-slate-200 gap-6 text-sm font-semibold text-slate-600">
        <button
          onClick={() => setActiveTab("RUNS")}
          className={`pb-3 flex items-center gap-2 transition border-b-2 ${
            activeTab === "RUNS"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Layers className="w-4 h-4" />
          Payroll Runs & Approvals
          {runs.length > 0 && (
            <span className="px-2 py-0.5 text-3xs rounded-full bg-slate-100 text-slate-600 font-mono">
              {runs.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("REVISIONS")}
          className={`pb-3 flex items-center gap-2 transition border-b-2 ${
            activeTab === "REVISIONS"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <FileText className="w-4 h-4" />
          Salary Revisions
          {revisions.length > 0 && (
            <span className="px-2 py-0.5 text-3xs rounded-full bg-indigo-50 text-indigo-600 font-mono">
              {revisions.length}
            </span>
          )}
        </button>

        <button
          onClick={() => setActiveTab("BUDGET")}
          className={`pb-3 flex items-center gap-2 transition border-b-2 ${
            activeTab === "BUDGET"
              ? "border-indigo-600 text-indigo-600"
              : "border-transparent text-slate-500 hover:text-slate-800"
          }`}
        >
          <Building className="w-4 h-4" />
          Job Budget vs Actual
        </button>
      </div>

      {/* ========================================================================= */}
      {/* TAB 1: PAYROLL RUNS & APPROVALS                                           */}
      {/* ========================================================================= */}
      {activeTab === "RUNS" && (
        <div className="space-y-6">
          {/* Top Runs Selector Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 flex flex-wrap items-center justify-between gap-4">
            <div className="flex items-center gap-3 flex-wrap">
              <span className="text-xs font-bold uppercase text-slate-500">Select Month Run:</span>
              <div className="flex gap-2 flex-wrap">
                {runs.map((r) => {
                  const isSel = r.id === selectedRunId;
                  const isDraft = r.status === "DRAFT";
                  return (
                    <button
                      key={r.id}
                      onClick={() => setSelectedRunId(r.id)}
                      className={`px-3 py-1.5 rounded-lg text-xs font-medium border flex items-center gap-2 transition ${
                        isSel
                          ? "bg-indigo-50 border-indigo-400 text-indigo-900 shadow-2xs font-bold"
                          : "bg-slate-50 border-slate-200 text-slate-600 hover:bg-slate-100"
                      }`}
                    >
                      <span>{r.period_start.substring(0, 7)}</span>
                      <span className="font-mono text-3xs px-1.5 py-0.2 bg-white rounded border border-slate-200">
                        Run #{r.run_no}
                      </span>
                      {isDraft ? (
                        <span className="text-amber-700 bg-amber-100 px-1.5 py-0.2 rounded text-3xs font-bold">
                          DRAFT
                        </span>
                      ) : (
                        <span className="text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded text-3xs font-bold flex items-center gap-0.5">
                          <Check className="w-3 h-3" /> APPROVED
                        </span>
                      )}
                    </button>
                  );
                })}
              </div>
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={fetchRuns}
                className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-500 transition"
                title="Refresh Runs"
              >
                <RefreshCw className={`w-4 h-4 ${runsLoading ? "animate-spin text-indigo-600" : ""}`} />
              </button>
            </div>
          </div>

          {selectedRunDetail ? (
            <div className="space-y-6">
              {/* Run Overview Card */}
              <div className="bg-white rounded-2xl border border-slate-200 p-6 shadow-xs space-y-6">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 border-b border-slate-100 pb-4">
                  <div>
                    <div className="flex items-center gap-3">
                      <h2 className="text-lg font-bold text-slate-900">
                        Payroll Run #{selectedRunDetail.run.run_no} ({selectedRunDetail.run.country})
                      </h2>
                      {selectedRunDetail.run.status === "DRAFT" ? (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-amber-50 text-amber-700 border border-amber-200">
                          DRAFT (Unapproved)
                        </span>
                      ) : (
                        <span className="px-2.5 py-0.5 rounded-full text-xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                          <Lock className="w-3.5 h-3.5" /> APPROVED SNAPSHOT
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-1 font-mono">
                      Period: {selectedRunDetail.run.period_start} → {selectedRunDetail.run.period_end} • Created:{" "}
                      {new Date(selectedRunDetail.run.created_at).toLocaleString()}
                    </p>
                  </div>

                  {/* Actions for Run */}
                  <div className="flex items-center gap-2 flex-wrap">
                    {selectedRunDetail.run.status === "DRAFT" && isAdmin && (
                      <>
                        <button
                          onClick={handleRerunDraft}
                          className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition"
                          title="Re-run draft to recalculate attendance and pick up newly approved overtime"
                        >
                          <RefreshCw className="w-3.5 h-3.5" />
                          Re-Run Draft
                        </button>

                        <button
                          onClick={() => setApproveModalOpen(true)}
                          className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition"
                        >
                          <CheckCircle2 className="w-4 h-4" />
                          Approve Payroll
                        </button>
                      </>
                    )}

                    {selectedRunDetail.run.status === "APPROVED" && (
                      <div className="text-xs text-slate-500 bg-slate-50 px-3 py-1.5 rounded-lg border border-slate-200 flex items-center gap-1.5 font-medium">
                        <Lock className="w-3.5 h-3.5 text-emerald-600" />
                        <span>Locked on {new Date(selectedRunDetail.run.approved_at || "").toLocaleDateString()}</span>
                      </div>
                    )}
                  </div>
                </div>

                {/* KPI Metrics */}
                <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-3">
                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-3xs uppercase font-bold text-slate-400 block">Workers</span>
                    <span className="text-lg font-bold text-slate-900 font-mono">
                      {selectedRunDetail.run.record_count}
                    </span>
                  </div>

                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-3xs uppercase font-bold text-slate-400 block">Gross Payroll</span>
                    <span className="text-lg font-bold text-slate-900 font-mono">
                      ${Number(selectedRunDetail.run.total_gross_pay || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-3xs uppercase font-bold text-slate-400 block">Net Employee Pay</span>
                    <span className="text-lg font-bold text-indigo-700 font-mono">
                      ${Number(selectedRunDetail.run.total_net_pay || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-3xs uppercase font-bold text-slate-400 block">Overtime Paid</span>
                    <span className="text-lg font-bold text-amber-700 font-mono">
                      ${Number(
                        (selectedRunDetail.records || []).reduce((acc, r) => acc + Number(r.ot1_amount || 0) + Number(r.ot2_amount || 0), 0)
                      ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100">
                    <span className="text-3xs uppercase font-bold text-slate-400 block">Missed Deductions</span>
                    <span className="text-lg font-bold text-rose-700 font-mono">
                      ${Number(
                        (selectedRunDetail.records || []).reduce((acc, r) => acc + Number(r.missed_hours_deduction || 0), 0)
                      ).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>

                  <div className="bg-indigo-50/60 p-3.5 rounded-xl border border-indigo-100">
                    <span className="text-3xs uppercase font-bold text-indigo-600 block">Employer Cost (+5% OH)</span>
                    <span className="text-lg font-bold text-indigo-900 font-mono">
                      ${Number(selectedRunDetail.run.total_employer_cost || 0).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                    </span>
                  </div>
                </div>

                {/* Issues Notification Panel */}
                {runIssues && (runIssues.unapproved_overtime_count > 0 || runIssues.missing_salary_structure_count > 0) && (
                  <div className="bg-amber-50 border border-amber-200 rounded-xl p-4 text-xs space-y-2">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2 text-amber-900 font-bold">
                        <AlertTriangle className="w-4 h-4 text-amber-600" />
                        <span>
                          Payroll Draft Issues ({runIssues.unapproved_overtime_count} unapproved overtime,{" "}
                          {runIssues.missing_salary_structure_count} missing salary structure)
                        </span>
                      </div>
                      <button
                        onClick={() => setIssuesOpen(!issuesOpen)}
                        className="text-amber-800 font-semibold hover:underline flex items-center gap-1 text-3xs uppercase tracking-wider"
                      >
                        {issuesOpen ? "Hide Issues" : "Inspect Issues"}
                        {issuesOpen ? <ChevronDown className="w-3.5 h-3.5" /> : <ChevronRight className="w-3.5 h-3.5" />}
                      </button>
                    </div>

                    <p className="text-amber-800 leading-relaxed text-3xs">
                      Unapproved overtime is held back and not included in pay until approved in the Attendance Approvals inbox.
                      Approving the draft with pending overtime will exclude those overtime hours from this month's slip.
                    </p>

                    {issuesOpen && (
                      <div className="pt-2 border-t border-amber-200/60 space-y-1.5 max-h-48 overflow-y-auto">
                        {runIssues.issues.map((iss, i) => (
                          <div key={i} className="flex items-center justify-between bg-white/70 p-2 rounded border border-amber-200 text-3xs">
                            <div>
                              <span className="font-bold text-slate-800">{iss.employee_name}</span> ({iss.tally_id})
                              {iss.work_date && <span className="text-slate-500 ml-1.5 font-mono">Date: {iss.work_date}</span>}
                              <span className="block text-amber-800 mt-0.5">{iss.description}</span>
                            </div>
                            <span className="text-indigo-600 font-medium">{iss.suggested_action}</span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </div>

              {/* Worker Records Table */}
              <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
                <div className="p-4 border-b border-slate-100 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                  <div className="flex items-center gap-2">
                    <h3 className="text-sm font-bold text-slate-900">Worker Payroll Records</h3>
                    <span className="text-xs bg-slate-100 text-slate-600 px-2 py-0.5 rounded-full font-mono">
                      {filteredRecords.length} workers
                    </span>
                  </div>

                  <div className="relative w-full sm:w-64">
                    <Search className="w-4 h-4 text-slate-400 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      placeholder="Search worker name or ID..."
                      value={recordSearch}
                      onChange={(e) => setRecordSearch(e.target.value)}
                      className="w-full pl-9 pr-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg focus:outline-none focus:ring-1 focus:ring-indigo-500"
                    />
                  </div>
                </div>

                <div className="overflow-x-auto">
                  <table className="w-full text-left border-collapse text-xs">
                    <thead>
                      <tr className="bg-slate-50/70 border-b border-slate-200 text-3xs font-bold uppercase text-slate-500">
                        <th className="py-2.5 px-4">Worker</th>
                        <th className="py-2.5 px-3">Role</th>
                        <th className="py-2.5 px-3">Std / Worked</th>
                        <th className="py-2.5 px-3">Missed (Ded)</th>
                        <th className="py-2.5 px-3">OT1 (Normal)</th>
                        <th className="py-2.5 px-3">OT2 (Holiday)</th>
                        <th className="py-2.5 px-3">Gross Pay</th>
                        <th className="py-2.5 px-3">Net Pay</th>
                        <th className="py-2.5 px-3">Total Staff Cost</th>
                        <th className="py-2.5 px-4 text-right">Details</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-slate-100">
                      {filteredRecords.map((r) => (
                        <tr key={r.id} className="hover:bg-slate-50/60 transition">
                          <td className="py-2.5 px-4">
                            <span className="font-bold text-slate-900 block">{r.employee_name}</span>
                            <span className="text-3xs font-mono text-slate-500">{r.employee_tally_id}</span>
                          </td>
                          <td className="py-2.5 px-3">
                            <span className="px-2 py-0.5 rounded bg-slate-100 text-slate-700 text-3xs font-semibold">
                              {r.employee_role}
                            </span>
                          </td>
                          <td className="py-2.5 px-3 font-mono">
                            <span>{r.standard_monthly_hours}h</span> /{" "}
                            <span className="font-semibold text-slate-800">{r.actual_worked_hours}h</span>
                          </td>
                          <td className="py-2.5 px-3 font-mono">
                            {Number(r.missed_hours) > 0 ? (
                              <span className="text-rose-600 font-semibold">
                                {r.missed_hours}h (-${Number(r.missed_hours_deduction).toFixed(2)})
                              </span>
                            ) : (
                              <span className="text-slate-400">0h</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-mono">
                            {Number(r.ot1_hours) > 0 ? (
                              <span className="text-amber-700 font-semibold">
                                {r.ot1_hours}h (${Number(r.ot1_amount).toFixed(2)})
                              </span>
                            ) : (
                              <span className="text-slate-400">0h</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-mono">
                            {Number(r.ot2_hours) > 0 ? (
                              <span className="text-indigo-700 font-semibold">
                                {r.ot2_hours}h (${Number(r.ot2_amount).toFixed(2)})
                              </span>
                            ) : (
                              <span className="text-slate-400">0h</span>
                            )}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold text-slate-900">
                            ${Number(r.gross_pay).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-bold text-indigo-700">
                            ${Number(r.net_pay).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-3 font-mono font-semibold text-slate-800">
                            ${Number(r.final_total_staff_cost).toFixed(2)}
                          </td>
                          <td className="py-2.5 px-4 text-right">
                            <button
                              onClick={() => setSelectedRecord(r)}
                              className="px-2.5 py-1 text-3xs font-semibold bg-indigo-50 text-indigo-600 rounded-lg hover:bg-indigo-100 transition"
                            >
                              Breakdown
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </div>
          ) : (
            <div className="bg-white p-12 text-center rounded-2xl border border-slate-200 text-slate-400 space-y-2">
              <Calendar className="w-8 h-8 mx-auto text-slate-300" />
              <p className="text-sm">No payroll runs found. Click "Generate Draft Run" to create the first monthly draft.</p>
            </div>
          )}
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 2: SALARY REVISIONS                                                   */}
      {/* ========================================================================= */}
      {activeTab === "REVISIONS" && (
        <div className="space-y-6">
          {/* Revisions Control Bar */}
          <div className="bg-white p-5 rounded-2xl border border-slate-200 shadow-xs flex flex-col md:flex-row md:items-center justify-between gap-4">
            <div className="flex items-center gap-4 flex-wrap">
              <div>
                <label className="text-3xs uppercase font-bold text-slate-400 block mb-1">Select Revision Code</label>
                <select
                  value={selectedRevisionCode}
                  onChange={(e) => setSelectedRevisionCode(e.target.value)}
                  className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg font-bold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500"
                >
                  {revisions.map((rev) => (
                    <option key={rev.code} value={rev.code}>
                      {rev.code} ({rev.name}) - {rev.country}
                    </option>
                  ))}
                </select>
              </div>

              {selectedRevisionCode && (
                <div className="text-xs text-slate-500 space-y-0.5">
                  <span className="font-semibold text-slate-700 block">
                    Active Effective Date:{" "}
                    {revisions.find((r) => r.code === selectedRevisionCode)?.effective_from}
                  </span>
                  <span className="text-3xs">
                    {revisionsLoading ? "Loading lines..." : `${activeRevisionLines.length} configured staff grade pricing lines`}
                  </span>
                </div>
              )}
            </div>

            <div className="flex items-center gap-2">
              <button
                onClick={handleExportRevisionTemplate}
                className="px-3 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold flex items-center gap-1.5 transition"
                title="Export pre-filled sheet with target revision code"
              >
                <Download className="w-3.5 h-3.5" />
                Export Template
              </button>

              {isAdmin && (
                <button
                  onClick={() => {
                    setTargetRevisionInput(`${selectedRevisionCode || "REV-2026"}-V2`);
                    setDiffModalOpen(true);
                  }}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold flex items-center gap-1.5 shadow-xs transition"
                >
                  <Upload className="w-3.5 h-3.5" />
                  Import Revision & Diff
                </button>
              )}
            </div>
          </div>

          {/* Revision Grade Lines Table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">
                  Grade Cost Pricing Lines ({selectedRevisionCode})
                </h3>
                <p className="text-3xs text-slate-500">
                  Defines planned hourly cost used to price labor budgets for worksites and tenders.
                </p>
              </div>

              <div className="flex items-center gap-1 text-3xs text-indigo-600 bg-indigo-50 px-2.5 py-1 rounded-lg">
                <Info className="w-3.5 h-3.5" />
                <span>Planned Cost = (Salary + Provisions + 5% OH) / 208h</span>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50/70 border-b border-slate-200 text-3xs font-bold uppercase text-slate-500">
                    <th className="py-2.5 px-4">Grade Code</th>
                    <th className="py-2.5 px-3">Title / Group</th>
                    <th className="py-2.5 px-3">Basic Salary</th>
                    <th className="py-2.5 px-3">Allowances (Spec/OT/Bon)</th>
                    <th className="py-2.5 px-3">Provisions (Visa/Air/Med/Acc)</th>
                    <th className="py-2.5 px-4 font-bold text-indigo-900">Planned Hourly Cost</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {activeRevisionLines.map((line) => {
                    const totalAllowances =
                      Number(line.special_allowance || 0) +
                      Number(line.fixed_ot_amount || 0) +
                      Number(line.bonus || 0);
                    const totalProvisions =
                      Number(line.visa_provision || 0) +
                      Number(line.air_ticket_provision || 0) +
                      Number(line.uniform_provision || 0) +
                      Number(line.medical_provision || 0) +
                      Number(line.accommodation_provision || 0);
                    return (
                      <tr key={line.grade_code} className="hover:bg-slate-50/60 transition">
                        <td className="py-2.5 px-4 font-mono font-bold text-slate-900">
                          {line.grade_code}
                        </td>
                        <td className="py-2.5 px-3 text-slate-700">
                          {line.grade_group_title || "--"}
                        </td>
                        <td className="py-2.5 px-3 font-mono font-semibold text-slate-800">
                          ${Number(line.basic_salary).toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-600">
                          ${totalAllowances.toFixed(2)}
                        </td>
                        <td className="py-2.5 px-3 font-mono text-slate-600">
                          ${totalProvisions.toFixed(2)}
                        </td>
                        <td className="py-2.5 px-4 font-mono font-extrabold text-indigo-700 bg-indigo-50/30">
                          ${Number(line.planned_hourly_cost).toFixed(2)} / hr
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* TAB 3: JOB BUDGET VS ACTUAL                                               */}
      {/* ========================================================================= */}
      {activeTab === "BUDGET" && (
        <div className="space-y-6">
          {/* Important Notice Banner: Provision Basis Difference */}
          <div className="bg-amber-50/80 border border-amber-300 rounded-2xl p-4 flex items-start gap-3 shadow-2xs">
            <Info className="w-5 h-5 text-amber-700 shrink-0 mt-0.5" />
            <div className="text-xs space-y-1">
              <span className="font-bold text-amber-900 block">
                Commercial Budget vs Actual Cost Basis Distinction
              </span>
              <p className="text-amber-800 leading-relaxed text-3xs">
                <strong>Planned Job Budgets</strong> use static commercial provisions explicitly specified in the active{" "}
                <em>Salary Revision</em> file for tender pricing. In contrast, <strong>Actual Allocated Costs</strong> use
                dynamic statutory employer provisions (gratuity accrual, leave salary, and company provisions) derived from live
                company settings and attendance records.
              </p>
            </div>
          </div>

          {/* Filter Bar */}
          <div className="bg-white p-4 rounded-xl border border-slate-200 flex items-center justify-between gap-4">
            <div className="flex items-center gap-3">
              <label className="text-3xs uppercase font-bold text-slate-400">Country:</label>
              <select
                value={countryBudgetFilter}
                onChange={(e) => setCountryBudgetFilter(e.target.value)}
                className="px-3 py-1.5 text-xs bg-slate-50 border border-slate-200 rounded-lg font-bold text-slate-700 focus:outline-none"
              >
                <option value="AE">United Arab Emirates (AE)</option>
                <option value="SA">Saudi Arabia (SA)</option>
                <option value="QA">Qatar (QA)</option>
              </select>
            </div>

            <button
              onClick={fetchBudgetVsActual}
              className="p-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 text-slate-500 transition"
              title="Refresh Budgets"
            >
              <RefreshCw className={`w-4 h-4 ${budgetLoading ? "animate-spin text-indigo-600" : ""}`} />
            </button>
          </div>

          {/* Worksites Budget Table */}
          <div className="bg-white rounded-2xl border border-slate-200 shadow-xs overflow-hidden">
            <div className="p-4 border-b border-slate-100 flex items-center justify-between">
              <div>
                <h3 className="text-sm font-bold text-slate-900">Worksite Labor Budget vs Actual Variance</h3>
                <p className="text-3xs text-slate-500">
                  Switch the assigned revision code dropdown to dynamically reprice contract budget upon renewal.
                </p>
              </div>
            </div>

            <div className="overflow-x-auto">
              <table className="w-full text-left border-collapse text-xs">
                <thead>
                  <tr className="bg-slate-50/70 border-b border-slate-200 text-3xs font-bold uppercase text-slate-500">
                    <th className="py-2.5 px-4">Worksite</th>
                    <th className="py-2.5 px-3">Assigned Revision Code</th>
                    <th className="py-2.5 px-3">Annual Planned Hours</th>
                    <th className="py-2.5 px-3">Annual Labor Budget</th>
                    <th className="py-2.5 px-3">Pro-Rated Budget (YTD)</th>
                    <th className="py-2.5 px-3">Actual Allocated Cost</th>
                    <th className="py-2.5 px-4">Variance ($ / %)</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {budgetItems.map((item) => (
                    <tr key={item.worksite_id} className="hover:bg-slate-50/60 transition">
                      <td className="py-2.5 px-4">
                        <span className="font-bold text-slate-900 block">{item.job_name}</span>
                        <span className="text-3xs font-mono text-slate-500">{item.job_number}</span>
                        {item.is_custom_budget_override && (
                          <span className="inline-block mt-0.5 px-1.5 py-0.2 bg-amber-100 text-amber-800 rounded text-3xs font-semibold">
                            Manual Override
                          </span>
                        )}
                      </td>

                      {/* Revision Code Binding Dropdown */}
                      <td className="py-2.5 px-3">
                        {isAdmin ? (
                          <select
                            value={item.assigned_revision_code || ""}
                            onChange={(e) => handleUpdateWorksiteRevision(item.worksite_id, e.target.value)}
                            disabled={updatingWorksiteRevId === item.worksite_id}
                            className="px-2 py-1 bg-slate-50 border border-slate-200 rounded text-xs font-mono font-semibold text-slate-800 focus:outline-none focus:ring-1 focus:ring-indigo-500 disabled:opacity-50"
                          >
                            <option value="">Default (Active Country Rev)</option>
                            {revisions.map((rev) => (
                              <option key={rev.code} value={rev.code}>
                                {rev.code}
                              </option>
                            ))}
                          </select>
                        ) : (
                          <span className="font-mono font-semibold text-slate-700">
                            {item.assigned_revision_code || "Default"}
                          </span>
                        )}
                      </td>

                      <td className="py-2.5 px-3 font-mono font-semibold text-slate-800">
                        {Number(item.annual_planned_man_hours).toLocaleString()}h
                      </td>

                      <td className="py-2.5 px-3 font-mono font-bold text-slate-900">
                        ${Number(item.annual_labor_budget).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>

                      <td className="py-2.5 px-3 font-mono text-slate-700">
                        ${Number(item.pro_rated_budget).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>

                      <td className="py-2.5 px-3 font-mono font-bold text-indigo-700">
                        ${Number(item.actual_allocated_cost).toLocaleString(undefined, { minimumFractionDigits: 2 })}
                      </td>

                      <td className="py-2.5 px-4">
                        <div className="flex items-center gap-1.5">
                          {item.is_under_budget ? (
                            <span className="px-2 py-0.5 rounded-full text-3xs font-bold bg-emerald-50 text-emerald-700 border border-emerald-200 flex items-center gap-1">
                              <TrendingDown className="w-3 h-3" />
                              Under: ${Math.abs(item.variance_amount).toFixed(2)} ({item.variance_percent.toFixed(1)}%)
                            </span>
                          ) : (
                            <span className="px-2 py-0.5 rounded-full text-3xs font-bold bg-rose-50 text-rose-700 border border-rose-200 flex items-center gap-1">
                              <TrendingUp className="w-3 h-3" />
                              Over: ${Math.abs(item.variance_amount).toFixed(2)} ({item.variance_percent.toFixed(1)}%)
                            </span>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 1: WORKER RECORD DETAIL DRAWER                                      */}
      {/* ========================================================================= */}
      {selectedRecord && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex justify-end z-50">
          <div className="bg-white w-full max-w-xl h-full shadow-2xl flex flex-col overflow-hidden animate-in slide-in-from-right">
            {/* Header */}
            <div className="p-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/70">
              <div>
                <h3 className="text-base font-bold text-slate-900">{selectedRecord.employee_name}</h3>
                <p className="text-xs text-slate-500 font-mono">
                  {selectedRecord.employee_tally_id} • {selectedRecord.employee_role}
                </p>
              </div>
              <button
                onClick={() => setSelectedRecord(null)}
                className="p-1 rounded-lg hover:bg-slate-200 text-slate-500"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Scrollable Content */}
            <div className="p-6 overflow-y-auto space-y-6 flex-1 text-xs">
              {/* Employee Earnings & Deductions */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider">
                  Employee Monthly Earnings
                </h4>

                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-2">
                  <div className="flex justify-between">
                    <span className="text-slate-600">Basic Salary:</span>
                    <span className="font-mono font-bold">${Number(selectedRecord.basic_salary).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Special Allowance:</span>
                    <span className="font-mono">${Number(selectedRecord.special_allowance).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Fixed Overtime:</span>
                    <span className="font-mono">${Number(selectedRecord.fixed_ot_amount).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-slate-600">Bonus:</span>
                    <span className="font-mono">${Number(selectedRecord.bonus).toFixed(2)}</span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 pt-1 font-bold text-slate-900">
                    <span>Base Salary Portion:</span>
                    <span className="font-mono">${Number(selectedRecord.salary_portion).toFixed(2)}</span>
                  </div>
                </div>

                {/* Overtime Breakdown */}
                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-2">
                  <div className="flex justify-between text-slate-600">
                    <span>OT1 (Normal Hours &gt; Std):</span>
                    <span className="font-mono">
                      {selectedRecord.ot1_hours}h × ${Number(selectedRecord.ot1_rate).toFixed(2)} ={" "}
                      <strong className="text-slate-900">${Number(selectedRecord.ot1_amount).toFixed(2)}</strong>
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>OT2 (Holiday & Weekly Off):</span>
                    <span className="font-mono">
                      {selectedRecord.ot2_hours}h × ${Number(selectedRecord.ot2_rate).toFixed(2)} ={" "}
                      <strong className="text-slate-900">${Number(selectedRecord.ot2_amount).toFixed(2)}</strong>
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 pt-1 font-bold text-slate-900">
                    <span>Gross Pay:</span>
                    <span className="font-mono">${Number(selectedRecord.gross_pay).toFixed(2)}</span>
                  </div>
                </div>

                {/* Missed Hours Deductions */}
                <div className="bg-rose-50/60 p-3.5 rounded-xl border border-rose-100 space-y-1.5 text-rose-900">
                  <div className="flex justify-between">
                    <span>Missed Hours ({selectedRecord.missed_hours}h @ Basic/208):</span>
                    <span className="font-mono font-bold">
                      -${Number(selectedRecord.missed_hours_deduction).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-rose-200/60 pt-1 font-bold text-sm text-indigo-900">
                    <span>Final Net Pay:</span>
                    <span className="font-mono">${Number(selectedRecord.net_pay).toFixed(2)}</span>
                  </div>
                </div>
              </div>

              {/* Employer Statutory Provisions & Staff Cost */}
              <div className="space-y-3">
                <h4 className="text-xs font-bold uppercase text-slate-400 tracking-wider">
                  Employer Provisions & Total Staff Cost
                </h4>

                <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-2">
                  <div className="flex justify-between text-slate-600">
                    <span>Gratuity Provision (21/12):</span>
                    <span className="font-mono font-semibold">
                      ${Number(selectedRecord.gratuity_provision).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>Leave Salary Provision (30/12):</span>
                    <span className="font-mono font-semibold">
                      ${Number(selectedRecord.leave_salary_provision).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>Company Provisions (5 Items):</span>
                    <span className="font-mono font-semibold">
                      ${Number(selectedRecord.company_provisions_total).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between text-slate-600">
                    <span>HR Overhead (5% of Subtotal):</span>
                    <span className="font-mono font-semibold">
                      ${Number(selectedRecord.hr_overhead_amount).toFixed(2)}
                    </span>
                  </div>
                  <div className="flex justify-between border-t border-slate-200 pt-1 font-bold text-sm text-indigo-950">
                    <span>Final Total Staff Cost:</span>
                    <span className="font-mono">${Number(selectedRecord.final_total_staff_cost).toFixed(2)}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 2: GENERATE DRAFT PAYROLL                                           */}
      {/* ========================================================================= */}
      {generateModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex justify-between items-center">
              <h3 className="text-base font-bold text-slate-900">Generate Monthly Payroll Draft</h3>
              <button onClick={() => setGenerateModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-3 text-xs">
              <div>
                <label className="text-slate-700 font-semibold block mb-1">Country</label>
                <select
                  value={genCountry}
                  onChange={(e) => setGenCountry(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-bold"
                >
                  <option value="AE">United Arab Emirates (AE)</option>
                  <option value="SA">Saudi Arabia (SA)</option>
                  <option value="QA">Qatar (QA)</option>
                </select>
              </div>

              <div className="grid grid-cols-2 gap-3">
                <div>
                  <label className="text-slate-700 font-semibold block mb-1">Period Start</label>
                  <input
                    type="date"
                    value={genPeriodStart}
                    onChange={(e) => setGenPeriodStart(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-mono"
                  />
                </div>
                <div>
                  <label className="text-slate-700 font-semibold block mb-1">Period End</label>
                  <input
                    type="date"
                    value={genPeriodEnd}
                    onChange={(e) => setGenPeriodEnd(e.target.value)}
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-mono"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-700 font-semibold block mb-1">Notes / Description (Optional)</label>
                <input
                  type="text"
                  placeholder="e.g. October 2026 Regular Payroll"
                  value={genNotes}
                  onChange={(e) => setGenNotes(e.target.value)}
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg"
                />
              </div>
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setGenerateModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleGenerateDraft}
                disabled={generating}
                className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold disabled:opacity-50"
              >
                {generating ? "Calculating..." : "Generate Draft"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 3: APPROVE PAYROLL CONFIRMATION                                     */}
      {/* ========================================================================= */}
      {approveModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-md w-full p-6 shadow-2xl space-y-4">
            <div className="flex items-center gap-3 text-emerald-600">
              <Lock className="w-6 h-6" />
              <h3 className="text-base font-bold text-slate-900">Approve & Lock Payroll Run</h3>
            </div>

            <div className="bg-amber-50 p-3.5 rounded-xl border border-amber-200 text-xs text-amber-900 space-y-1.5">
              <span className="font-bold block">Important Notice:</span>
              <p className="text-3xs leading-relaxed">
                Approving will freeze this payroll run as an immutable audit snapshot. All worker attendance records
                for this period will be <strong>locked</strong> against automatic recomputation.
              </p>
            </div>

            <div className="text-xs space-y-1">
              <label className="text-slate-700 font-semibold block">Approval Notes (Optional)</label>
              <textarea
                rows={2}
                placeholder="e.g. Reviewed and verified against operations and timecards"
                value={approveNotes}
                onChange={(e) => setApproveNotes(e.target.value)}
                className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg text-xs"
              />
            </div>

            <div className="flex justify-end gap-2 pt-2 border-t border-slate-100">
              <button
                onClick={() => setApproveModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              <button
                onClick={handleApproveRun}
                disabled={approving}
                className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold disabled:opacity-50"
              >
                {approving ? "Freezing..." : "Confirm Approval"}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 4: SALARY REVISION IMPORT & SIDE-BY-SIDE DIFF                       */}
      {/* ========================================================================= */}
      {diffModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-4xl w-full p-6 shadow-2xl space-y-4 max-h-[90vh] flex flex-col">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <div>
                <h3 className="text-base font-bold text-slate-900">Import Revision & Side-by-Side Diff</h3>
                <p className="text-3xs text-slate-500">
                  Compare new revision numbers against base revision{" "}
                  <strong className="text-indigo-600 font-mono">{selectedRevisionCode}</strong> before committing.
                </p>
              </div>
              <button onClick={() => setDiffModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="overflow-y-auto space-y-4 flex-1 text-xs">
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="text-slate-700 font-semibold block mb-1">Target Revision Code</label>
                  <input
                    type="text"
                    value={targetRevisionInput}
                    onChange={(e) => setTargetRevisionInput(e.target.value)}
                    placeholder="e.g. REV-2026-V2"
                    className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-mono font-bold"
                  />
                </div>
                <div>
                  <label className="text-slate-700 font-semibold block mb-1">Base Comparison Revision</label>
                  <input
                    type="text"
                    value={selectedRevisionCode}
                    disabled
                    className="w-full px-3 py-2 bg-slate-100 border border-slate-200 rounded-lg font-mono text-slate-500"
                  />
                </div>
              </div>

              <div>
                <label className="text-slate-700 font-semibold block mb-1">
                  Revision Lines (Paste JSON Array)
                </label>
                <textarea
                  rows={4}
                  value={diffInputJson}
                  onChange={(e) => setDiffInputJson(e.target.value)}
                  placeholder='[{"grade_code": "GE", "basic_salary": 1300, "special_allowance": 200, "fixed_ot_amount": 100, "bonus": 0, "visa_provision": 100, "air_ticket_provision": 75, "uniform_provision": 25, "medical_provision": 50, "accommodation_provision": 300}]'
                  className="w-full px-3 py-2 bg-slate-50 border border-slate-200 rounded-lg font-mono text-3xs"
                />
              </div>

              <div className="flex justify-between items-center">
                <button
                  onClick={handleRunDiffPreview}
                  disabled={diffLoading}
                  className="px-4 py-2 bg-indigo-600 hover:bg-indigo-700 text-white rounded-xl text-xs font-bold disabled:opacity-50"
                >
                  {diffLoading ? "Comparing..." : "Generate Diff Preview"}
                </button>
              </div>

              {/* Side-by-Side Diff Table */}
              {diffResult && (
                <div className="border border-slate-200 rounded-xl overflow-hidden mt-4">
                  <div className="bg-slate-50 p-2.5 border-b border-slate-200 font-bold text-3xs uppercase text-slate-500 flex justify-between">
                    <span>Side-by-Side Comparison</span>
                    <span>{diffResult.diffs.length} grades analyzed</span>
                  </div>
                  <div className="max-h-60 overflow-y-auto">
                    <table className="w-full text-left text-3xs border-collapse">
                      <thead>
                        <tr className="bg-slate-100/70 border-b border-slate-200 font-semibold text-slate-600">
                          <th className="py-2 px-3">Grade Code</th>
                          <th className="py-2 px-3">Status</th>
                          <th className="py-2 px-3">Field Changes (Red: Before → Green: After)</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {diffResult.diffs.map((d: any) => (
                          <tr key={d.grade_code} className="hover:bg-slate-50/60">
                            <td className="py-2 px-3 font-mono font-bold text-slate-900">{d.grade_code}</td>
                            <td className="py-2 px-3">
                              {d.status === "CHANGED" && (
                                <span className="px-1.5 py-0.5 bg-amber-100 text-amber-800 rounded font-bold">
                                  CHANGED
                                </span>
                              )}
                              {d.status === "ADDED" && (
                                <span className="px-1.5 py-0.5 bg-emerald-100 text-emerald-800 rounded font-bold">
                                  ADDED
                                </span>
                              )}
                              {d.status === "REMOVED" && (
                                <span className="px-1.5 py-0.5 bg-rose-100 text-rose-800 rounded font-bold">
                                  REMOVED
                                </span>
                              )}
                              {d.status === "UNCHANGED" && (
                                <span className="px-1.5 py-0.5 bg-slate-100 text-slate-600 rounded">
                                  UNCHANGED
                                </span>
                              )}
                            </td>
                            <td className="py-2 px-3 font-mono">
                              {Object.keys(d.field_diffs || {}).length > 0 ? (
                                <div className="space-y-0.5">
                                  {Object.entries(d.field_diffs).map(([field, change]: any) => (
                                    <div key={field} className="flex items-center gap-1.5">
                                      <span className="text-slate-500 font-sans">{field}:</span>
                                      <span className="bg-rose-100 text-rose-800 px-1 rounded line-through">
                                        {change.old}
                                      </span>
                                      <ArrowRight className="w-2.5 h-2.5 text-slate-400" />
                                      <span className="bg-emerald-100 text-emerald-800 px-1 rounded font-bold">
                                        {change.new}
                                      </span>
                                    </div>
                                  ))}
                                </div>
                              ) : (
                                <span className="text-slate-400">No numeric changes</span>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-slate-100">
              <button
                onClick={() => setDiffModalOpen(false)}
                className="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 rounded-xl text-xs font-semibold"
              >
                Cancel
              </button>
              {diffResult && (
                <button
                  onClick={handleSaveImportedRevision}
                  disabled={diffLoading}
                  className="px-4 py-2 bg-emerald-600 hover:bg-emerald-700 text-white rounded-xl text-xs font-bold disabled:opacity-50"
                >
                  Confirm & Save Revision
                </button>
              )}
            </div>
          </div>
        </div>
      )}

      {/* ========================================================================= */}
      {/* MODAL 5: INFORMATIVE FORMULA GUIDE MODAL                                  */}
      {/* ========================================================================= */}
      {formulaModalOpen && (
        <div className="fixed inset-0 bg-slate-900/50 backdrop-blur-xs flex items-center justify-center p-4 z-50">
          <div className="bg-white rounded-2xl max-w-2xl w-full p-6 shadow-2xl space-y-4 max-h-[85vh] overflow-y-auto">
            <div className="flex justify-between items-center border-b border-slate-100 pb-3">
              <div className="flex items-center gap-2 text-indigo-600">
                <Info className="w-5 h-5" />
                <h3 className="text-base font-bold text-slate-900">
                  Payroll Rules & Cost Allocation Formula Guide
                </h3>
              </div>
              <button onClick={() => setFormulaModalOpen(false)} className="text-slate-400 hover:text-slate-600">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4 text-xs leading-relaxed text-slate-700">
              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-1.5">
                <h4 className="font-bold text-indigo-900 text-xs">1. Overtime Calculation Basis</h4>
                <p className="text-3xs text-slate-600">
                  Under UAE / GCC labor standards, the standard monthly working hour divisor is <strong>208 hours</strong>{" "}
                  (calculated as 26 working days × 8 standard hours).
                </p>
                <div className="font-mono text-3xs bg-white p-2 rounded border border-slate-200 space-y-0.5">
                  <div><strong>OT1 Rate (Normal Days Beyond Std):</strong> (Basic Salary / 208) × 1.25</div>
                  <div><strong>OT2 Rate (Public Holidays & Weekly Off):</strong> (Basic Salary / 208) × 1.50</div>
                </div>
                <p className="text-3xs text-slate-500">
                  <em>Benchmark:</em> Basic of $1,100 yields an OT1 rate of $6.61/hr and OT2 rate of $7.93/hr.
                </p>
              </div>

              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-1.5">
                <h4 className="font-bold text-indigo-900 text-xs">2. Missed Hours & Leave Deductions</h4>
                <p className="text-3xs text-slate-600">
                  Workers are paid standard monthly salary portions. Missed hours (unpaid leave hours + shortfalls) are deducted
                  proportionately from pay using the formula:
                </p>
                <div className="font-mono text-3xs bg-white p-2 rounded border border-slate-200">
                  Deduction = Missed Hours × (Basic Salary / 208)
                </div>
                <p className="text-3xs text-slate-500">
                  Approved paid leaves (Annual, Sick) incur 0 deduction.
                </p>
              </div>

              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-1.5">
                <h4 className="font-bold text-indigo-900 text-xs">3. Employer Statutory Provisions & HR Overhead</h4>
                <p className="text-3xs text-slate-600">
                  Employer staff cost calculation includes statutory end-of-service gratuity and leave salary accruals:
                </p>
                <div className="font-mono text-3xs bg-white p-2 rounded border border-slate-200 space-y-0.5">
                  <div><strong>Gratuity Provision:</strong> (Basic Salary / 30) × (21 / 12)</div>
                  <div><strong>Leave Salary Provision:</strong> ((Basic + Housing Allowance) / 30) × (30 / 12)</div>
                  <div><strong>5 Company Provisions:</strong> Visa, Air Ticket, Uniform, Medical, Accommodation</div>
                  <div><strong>HR Overhead:</strong> 5% added to Total Staff Cost for the final figure.</div>
                </div>
              </div>

              <div className="bg-slate-50 p-3.5 rounded-xl border border-slate-100 space-y-1.5">
                <h4 className="font-bold text-indigo-900 text-xs">4. Job Budget Provision Basis Distinction</h4>
                <p className="text-3xs text-slate-600">
                  <strong>Planned Job Budgets</strong> use static commercial provisions explicitly specified in the active{" "}
                  <em>Salary Revision</em> file for tender pricing. In contrast, <strong>Actual Allocated Costs</strong> use
                  dynamic statutory employer provisions derived from live company settings and attendance records.
                </p>
              </div>
            </div>

            <div className="flex justify-end pt-2 border-t border-slate-100">
              <button
                onClick={() => setFormulaModalOpen(false)}
                className="px-4 py-2 bg-indigo-600 text-white rounded-xl text-xs font-bold hover:bg-indigo-700"
              >
                Close Guide
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
