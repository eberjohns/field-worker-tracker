import React, { useState, useEffect, useMemo, useRef } from "react";
import { useAuth } from "../context/AuthContext";
import {
  CalendarDays,
  ChevronLeft,
  ChevronRight,
  Users,
  Building2,
  AlertTriangle,
  CheckCircle2,
  Trash2,
  X,
  Loader2,
  Search,
  UserCheck,
  Sparkles,
  FileText,
  Plus,
  Undo2,
  Pin,
  Filter,
  RotateCcw,
  AlertCircle,
  Clock,
} from "lucide-react";
import {
  OperationalCoverageResponse,
  OperationalWorksiteRow,
  OperationalJobItemRow,
  OperationalDayCell,
  OperationalRosterResponse,
  OperationalRosterWorkerRow,
  OperationalShiftCreate,
  CandidateRecommendation,
} from "../features/planner/types";

function formatReadableWeek(weekStartStr: string): string {
  try {
    const parts = weekStartStr.split("-").map(Number);
    const start = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    const end = new Date(start);
    end.setUTCDate(start.getUTCDate() + 6);

    const monthName = start.toLocaleString("en-US", { month: "short", timeZone: "UTC" }).toUpperCase();
    const year = start.getUTCFullYear();
    const dayOfMonth = start.getUTCDate();
    const weekNum = Math.ceil(dayOfMonth / 7);

    const startDay = String(start.getUTCDate()).padStart(2, "0");
    const endDay = String(end.getUTCDate()).padStart(2, "0");
    const endMonth = end.toLocaleString("en-US", { month: "short", timeZone: "UTC" });

    return `Week ${weekNum} - ${monthName} ${year} (${startDay} - ${endDay} ${endMonth})`;
  } catch {
    return `Week of ${weekStartStr}`;
  }
}

function isSameWeekday(offDay: string | null | undefined, weekdayCode: string): boolean {
  if (!offDay || !weekdayCode) return false;
  const off = offDay.trim().toUpperCase();
  const code = weekdayCode.trim().toUpperCase();
  return off === code || off.startsWith(code) || code.startsWith(off);
}

interface SupervisorOption {
  id: string;
  name: string;
  tally_id?: string;
}

interface StagedWorkerAddition {
  tempId: string;
  employee_id: string;
  employee_name: string;
  tally_id?: string | null;
  staff_grade_description?: string;
  assigned_hours: number;
  override_reason: string;
  original_employee_id?: string | null;
  original_employee_name?: string | null;
  source: "OVERRIDE" | "DIRECT";
  is_rest_day?: boolean;
}

interface StagedBaseRemoval {
  employee_id: string;
  employee_name: string;
  assigned_hours: number;
  reason: string;
}

export const OperationalPlanner: React.FC = () => {
  const { token, user } = useAuth();

  // Navigation & Lens
  const [activeLens, setActiveLens] = useState<"COVERAGE" | "ROSTER">("COVERAGE");
  const [weekStartDate, setWeekStartDate] = useState<string>(() => {
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diff));
    return monday.toISOString().split("T")[0];
  });

  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>("");

  // Staffing Gaps & Reassignment Request Modal State
  const [staffingGaps, setStaffingGaps] = useState<any[]>([]);
  const [allEmployeesList, setAllEmployeesList] = useState<any[]>([]);
  const [reassignmentModalOpen, setReassignmentModalOpen] = useState<boolean>(false);
  const [reassignType, setReassignType] = useState<"REPLACE" | "MOVE" | "ADD" | "CANCEL">("REPLACE");
  const [reassignDateFrom, setReassignDateFrom] = useState<string>(() => {
    const d = new Date(Date.now() + 3 * 86400000);
    return d.toISOString().split("T")[0];
  });
  const [reassignDateTo, setReassignDateTo] = useState<string>(() => {
    const d = new Date(Date.now() + 3 * 86400000);
    return d.toISOString().split("T")[0];
  });
  const [reassignOrigEmpId, setReassignOrigEmpId] = useState<string>("");
  const [reassignNewEmpId, setReassignNewEmpId] = useState<string>("");
  const [reassignJobItemId, setReassignJobItemId] = useState<string>("");
  const [reassignReasonCategory, setReassignReasonCategory] = useState<string>("LEAVE_COVER");
  const [reassignReason, setReassignReason] = useState<string>("");
  const [reassignSubmitting, setReassignSubmitting] = useState<boolean>(false);
  const [reassignError, setReassignError] = useState<string | null>(null);
  const [reassignSuccess, setReassignSuccess] = useState<string | null>(null);
  const [reassignPreview, setReassignPreview] = useState<any | null>(null);
  const [previewLoading, setPreviewLoading] = useState<boolean>(false);
  const [highlightedJobItemId, setHighlightedJobItemId] = useState<string | null>(null);
  const [recentReassignments, setRecentReassignments] = useState<any[]>([]);
  const [showReassignmentsHistory, setShowReassignmentsHistory] = useState<boolean>(false);

  // Check notice days (>= 3 days notice required)
  const noticeDays = useMemo(() => {
    if (!reassignDateFrom) return 0;
    const parts = reassignDateFrom.split("-").map(Number);
    const target = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
    const now = new Date();
    const todayUtc = new Date(Date.UTC(now.getFullYear(), now.getMonth(), now.getDate()));
    return Math.round((target.getTime() - todayUtc.getTime()) / (1000 * 3600 * 24));
  }, [reassignDateFrom]);

  // Pinning state
  const [pinnedWorksites, setPinnedWorksites] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem("fwt_pinned_worksites");
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch {
      return new Set();
    }
  });

  const togglePinWorksite = (id: string) => {
    setPinnedWorksites((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        localStorage.setItem("fwt_pinned_worksites", JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });
  };

  const [pinnedWorkers, setPinnedWorkers] = useState<Set<string>>(() => {
    try {
      const raw = localStorage.getItem("fwt_pinned_workers");
      return raw ? new Set(JSON.parse(raw)) : new Set();
    } catch {
      return new Set();
    }
  });

  const togglePinWorker = (id: string) => {
    setPinnedWorkers((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      try {
        localStorage.setItem("fwt_pinned_workers", JSON.stringify(Array.from(next)));
      } catch {}
      return next;
    });
  };

  // Worker Roster specific search & filters
  const [rosterSearchQuery, setRosterSearchQuery] = useState<string>("");
  const [selectedJobFilter, setSelectedJobFilter] = useState<string>("");
  const [groupBySupervisor, setGroupBySupervisor] = useState<boolean>(false);

  // Supervisor filter
  const [supervisorsList, setSupervisorsList] = useState<SupervisorOption[]>([]);
  const [selectedSupervisorId, setSelectedSupervisorId] = useState<string>("");

  // Data states
  const [coverageData, setCoverageData] = useState<OperationalCoverageResponse | null>(null);
  const [rosterData, setRosterData] = useState<OperationalRosterResponse | null>(null);

  // Modal State for Operational Action
  const [selectedCell, setSelectedCell] = useState<{
    worksite: OperationalWorksiteRow;
    item: OperationalJobItemRow;
    cell: OperationalDayCell;
  } | null>(null);

  const [replacementTargetId, setReplacementTargetId] = useState<string | null>(null);
  const [shiftHours, setShiftHours] = useState<string>("8.0");
  const [overrideReason, setOverrideReason] = useState<string>("");
  const [stagedRemovals, setStagedRemovals] = useState<Set<string>>(new Set());
  const [stagedAdditions, setStagedAdditions] = useState<StagedWorkerAddition[]>([]);
  const [stagedBaseRemovals, setStagedBaseRemovals] = useState<Map<string, StagedBaseRemoval>>(new Map());
  const [removingBaseWorkerId, setRemovingBaseWorkerId] = useState<string | null>(null);
  const [baseRemovalReasonInput, setBaseRemovalReasonInput] = useState<string>("");

  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [candidateSearch, setCandidateSearch] = useState<string>("");
  const [filterToSupervisorCrew, setFilterToSupervisorCrew] = useState<boolean>(true);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [savingShift, setSavingShift] = useState<boolean>(false);
  const [isRefreshing, setIsRefreshing] = useState<boolean>(false);

  const scrollPosRef = useRef<number>(0);

  // Fetch Operational Data
  const fetchOperationalData = async (silent: boolean = false) => {
    const hasExistingData = activeLens === "COVERAGE" ? !!coverageData : !!rosterData;
    const shouldSilent = silent || hasExistingData;
    if (!shouldSilent) setLoading(true);
    else setIsRefreshing(true);

    scrollPosRef.current = window.scrollY;
    setError(null);
    try {
      if (activeLens === "COVERAGE") {
        const res = await fetch(
          `/api/v1/operational-planner/coverage?week_start=${weekStartDate}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!res.ok) throw new Error("Failed to load Operational Coverage");
        const data: OperationalCoverageResponse = await res.json();
        setCoverageData(data);
      } else {
        const res = await fetch(
          `/api/v1/operational-planner/roster?week_start=${weekStartDate}`,
          { headers: { Authorization: `Bearer ${token}` } }
        );
        if (!res.ok) throw new Error("Failed to load Operational Roster");
        const data: OperationalRosterResponse = await res.json();
        setRosterData(data);
      }
    } catch (err: any) {
      setError(err.message || "An error occurred");
    } finally {
      if (!shouldSilent) setLoading(false);
      else setIsRefreshing(false);
      requestAnimationFrame(() => {
        if (scrollPosRef.current > 0) {
          window.scrollTo({ top: scrollPosRef.current, behavior: "instant" });
        }
      });
    }
  };

  // Fetch Supervisors
  const fetchSupervisors = async () => {
    try {
      const res = await fetch("/api/v1/employees?role=SUPERVISOR&limit=200", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const items = data.items || data || [];
        const list: SupervisorOption[] = items.map((emp: any) => ({
          id: emp.id,
          name: emp.name || emp.tally_id || "Supervisor",
          tally_id: emp.tally_id,
        }));
        setSupervisorsList(list);
      }
    } catch (e) {
      console.error("Failed to fetch supervisors:", e);
    }
  };

  // Fetch Staffing Gaps (TO_BE_COVERED slots from approved leave)
  const fetchStaffingGaps = async () => {
    try {
      const today = new Date().toISOString().split("T")[0];
      const future = new Date(Date.now() + 30 * 86400000).toISOString().split("T")[0];
      const res = await fetch(`/api/v1/staffing-gaps?from_date=${today}&to_date=${future}`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setStaffingGaps(data.gaps || []);
      }
    } catch (e) {
      console.error("Failed to fetch staffing gaps:", e);
    }
  };

  // Fetch all employees for reassignment dropdowns
  const fetchAllEmployees = async () => {
    try {
      const res = await fetch("/api/v1/employees?limit=500", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        const items = data.items || data || [];
        setAllEmployeesList(items);
      }
    } catch (e) {
      console.error("Failed to fetch all employees:", e);
    }
  };

  // Fetch recent temporary reassignments
  const fetchRecentReassignments = async () => {
    try {
      const res = await fetch("/api/v1/reassignment-requests", {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setRecentReassignments(data || []);
      }
    } catch (e) {
      console.error("Failed to fetch reassignments:", e);
    }
  };

  // Auto-focus on date / worker / job if passed via URL parameters
  useEffect(() => {
    const params = new URLSearchParams(window.location.search);
    const dateParam = params.get("date");
    const empParam = params.get("employee_id");
    const jobParam = params.get("job_item_id");
    const lensParam = params.get("lens");

    if (dateParam) {
      try {
        const parts = dateParam.split("-").map(Number);
        const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
        const day = d.getUTCDay();
        const diff = d.getUTCDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(d);
        monday.setUTCDate(diff);
        setWeekStartDate(monday.toISOString().split("T")[0]);
      } catch (e) {
        console.error("Invalid date query param", e);
      }
    }

    if (jobParam) {
      setHighlightedJobItemId(jobParam);
    }

    if (lensParam === "ROSTER") {
      setActiveLens("ROSTER");
      if (empParam) {
        setRosterSearchQuery(empParam);
      }
    } else {
      setActiveLens("COVERAGE");
    }
  }, []);

  useEffect(() => {
    if (token) {
      fetchOperationalData();
      fetchSupervisors();
      fetchStaffingGaps();
      fetchAllEmployees();
      fetchRecentReassignments();
    }
  }, [token, weekStartDate, activeLens]);

  // Focus on a specific reassignment in the planner grid
  const handleFocusReassignment = (item: any) => {
    if (item.date_from) {
      try {
        const parts = item.date_from.split("-").map(Number);
        const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2]));
        const day = d.getUTCDay();
        const diff = d.getUTCDate() - day + (day === 0 ? -6 : 1);
        const monday = new Date(d);
        monday.setUTCDate(diff);
        setWeekStartDate(monday.toISOString().split("T")[0]);
      } catch (e) {
        console.error("Invalid date on reassignment", e);
      }
    }
    setActiveLens("COVERAGE");
    if (item.target_job_item_id) {
      setHighlightedJobItemId(item.target_job_item_id);
    }
  };

  // Available job items for reassignment targets
  const availableJobItems = useMemo(() => {
    if (!coverageData?.worksites) return [];
    const list: { job_item_id: string; label: string }[] = [];
    for (const ws of coverageData.worksites) {
      for (const item of ws.items) {
        list.push({
          job_item_id: item.job_item_id,
          label: `${ws.job_number} - ${ws.job_name} (${item.sub_item_code} - ${item.staff_grade_description})`,
        });
      }
    }
    return list;
  }, [coverageData]);

  // Available employees for reassignment
  const availableEmployees = useMemo(() => {
    if (allEmployeesList.length > 0) return allEmployeesList;
    if (rosterData?.workers) {
      return rosterData.workers.map((w) => ({
        id: w.employee_id,
        name: w.name,
        tally_id: w.tally_id,
        staff_grade_description: w.staff_grade_description,
      }));
    }
    return [];
  }, [allEmployeesList, rosterData]);

  // Open Reassignment Modal pre-filled for a specific staffing gap
  const handleOpenReassignmentForGap = (gap: any) => {
    setReassignType("REPLACE");
    setReassignDateFrom(gap.work_date);
    setReassignDateTo(gap.work_date);
    setReassignOrigEmpId(gap.original_employee_id);
    setReassignJobItemId(gap.job_item_id);
    setReassignReasonCategory("LEAVE_COVER");
    setReassignReason(`Cover replacement for ${gap.original_employee_name}`);
    setReassignError(null);
    setReassignSuccess(null);
    setReassignPreview(null);
    setReassignmentModalOpen(true);
  };

  // Preview hours impact for reassignment
  const handlePreviewReassignment = async () => {
    if (!reassignNewEmpId || !reassignDateFrom || !reassignDateTo) return;
    setPreviewLoading(true);
    setReassignPreview(null);
    try {
      const payload: any = {
        employee_id: reassignNewEmpId,
        date_from: reassignDateFrom,
        date_to: reassignDateTo,
        additional_hours_per_day: 8.0,
      };
      if (reassignJobItemId) payload.target_job_item_id = reassignJobItemId;

      const res = await fetch("/api/v1/reassignment-requests/preview", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      if (res.ok) {
        const data = await res.json();
        setReassignPreview(data);
      }
    } catch (e) {
      console.error("Preview failed", e);
    } finally {
      setPreviewLoading(false);
    }
  };

  // Submit Reassignment Request (strictly validates >= 3 days notice per BR-SC-04)
  const handleCreateReassignment = async (e: React.FormEvent) => {
    e.preventDefault();
    setReassignError(null);
    setReassignSuccess(null);

    if (noticeDays < 3 && user?.role !== "ADMIN") {
      setReassignError("Notice is under 3 days. Requests with less than 3 days notice are strictly refused by company policy.");
      return;
    }

    if ((reassignType === "REPLACE" || reassignType === "MOVE" || reassignType === "CANCEL") && !reassignOrigEmpId) {
      setReassignError("Please select the original employee.");
      return;
    }

    if ((reassignType === "REPLACE" || reassignType === "ADD") && !reassignNewEmpId) {
      setReassignError("Please select the new / replacement employee.");
      return;
    }

    if ((reassignType === "REPLACE" || reassignType === "MOVE" || reassignType === "ADD") && !reassignJobItemId) {
      setReassignError("Please select the target worksite / job item.");
      return;
    }

    if (!reassignReason.trim()) {
      setReassignError("Please provide a reason for the reassignment.");
      return;
    }

    setReassignSubmitting(true);
    try {
      const payload: any = {
        reassignment_type: reassignType,
        date_from: reassignDateFrom,
        date_to: reassignDateTo,
        reason_category: reassignReasonCategory,
        reason: reassignReason.trim(),
      };
      if (reassignOrigEmpId) payload.original_employee_id = reassignOrigEmpId;
      if (reassignNewEmpId) payload.new_employee_id = reassignNewEmpId;
      if (reassignJobItemId) payload.target_job_item_id = reassignJobItemId;

      const res = await fetch("/api/v1/reassignment-requests", {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify(payload),
      });

      const data = await res.json();
      if (!res.ok) {
        const msg = data?.detail?.message || data?.detail || "Failed to create reassignment request";
        setReassignError(String(msg));
        return;
      }

      setReassignSuccess("Reassignment request submitted successfully! It is now pending review in the Approvals Inbox.");
      setTimeout(() => {
        setReassignmentModalOpen(false);
        setReassignSuccess(null);
        fetchOperationalData(true);
        fetchStaffingGaps();
      }, 1500);
    } catch (err: any) {
      setReassignError(err.message || "Network error submitting reassignment request.");
    } finally {
      setReassignSubmitting(false);
    }
  };

  // Week navigation helpers
  const handlePrevWeek = () => {
    scrollPosRef.current = window.scrollY;
    const parts = weekStartDate.split("-").map(Number);
    const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] - 7));
    setWeekStartDate(d.toISOString().split("T")[0]);
  };

  const handleNextWeek = () => {
    scrollPosRef.current = window.scrollY;
    const parts = weekStartDate.split("-").map(Number);
    const d = new Date(Date.UTC(parts[0], parts[1] - 1, parts[2] + 7));
    setWeekStartDate(d.toISOString().split("T")[0]);
  };

  const handleCurrentWeek = () => {
    scrollPosRef.current = window.scrollY;
    const now = new Date();
    const day = now.getDay();
    const diff = now.getDate() - day + (day === 0 ? -6 : 1);
    const monday = new Date(now.setDate(diff));
    setWeekStartDate(monday.toISOString().split("T")[0]);
  };

  // Open operational action modal on cell click
  const handleCellClick = async (
    ws: OperationalWorksiteRow,
    it: OperationalJobItemRow,
    cell: OperationalDayCell
  ) => {
    setSelectedCell({ worksite: ws, item: it, cell });
    setReplacementTargetId(null);
    setShiftHours(String(it.hours_per_occurrence || "8.0"));
    setOverrideReason("");
    setCandidateSearch("");
    setFilterToSupervisorCrew(Boolean(selectedSupervisorId));
    setStagedRemovals(new Set());
    setStagedAdditions([]);
    setStagedBaseRemovals(new Map());
    setRemovingBaseWorkerId(null);
    setBaseRemovalReasonInput("");

    // Load candidate recommendations for this item
    setLoadingCandidates(true);
    try {
      const res = await fetch(
        `/api/v1/job-items/${it.job_item_id}/recommendations?date=${cell.work_date}`,
        { headers: { Authorization: `Bearer ${token}` } }
      );
      if (res.ok) {
        const data = await res.json();
        setCandidates(data || []);
      }
    } catch (e) {
      console.error("Failed to load candidates", e);
    } finally {
      setLoadingCandidates(false);
    }
  };

  // Stage an operational shift deletion (or restore cancelled base shift)
  const handleStageRemoveShift = (shiftId: string) => {
    setStagedRemovals((prev) => {
      const next = new Set(prev);
      next.add(shiftId);
      return next;
    });
  };

  // Undo a staged removal
  const handleUndoRemoveShift = (shiftId: string) => {
    setStagedRemovals((prev) => {
      const next = new Set(prev);
      next.delete(shiftId);
      return next;
    });
  };

  // Base shift removal staging
  const handleConfirmStageBaseRemoval = (worker: { employee_id: string; employee_name: string; assigned_hours?: number | string }) => {
    if (!baseRemovalReasonInput.trim()) return;
    const defaultHours = Number(worker.assigned_hours) || Number(selectedCell?.item.hours_per_occurrence) || 8.0;
    setStagedBaseRemovals((prev) => {
      const next = new Map(prev);
      next.set(worker.employee_id, {
        employee_id: worker.employee_id,
        employee_name: worker.employee_name,
        assigned_hours: defaultHours,
        reason: baseRemovalReasonInput.trim(),
      });
      return next;
    });
    setRemovingBaseWorkerId(null);
    setBaseRemovalReasonInput("");
  };

  const handleUndoStageBaseRemoval = (workerId: string) => {
    setStagedBaseRemovals((prev) => {
      const next = new Map(prev);
      next.delete(workerId);
      return next;
    });
  };

  // Stage adding a worker
  const handleAddCandidateToStaged = (cand: CandidateRecommendation) => {
    const isReplacement = !!replacementTargetId;
    const targetWorker = isReplacement
      ? selectedCell?.cell.workers.find((w) => w.employee_id === replacementTargetId)
      : null;

    const defaultHours = Number(shiftHours) || Number(selectedCell?.item.hours_per_occurrence) || 8.0;
    const defaultReason = overrideReason.trim()
      ? overrideReason.trim()
      : isReplacement
      ? `Cover for ${targetWorker?.employee_name || "worker"}`
      : "Additional shift";

    const newAddition: StagedWorkerAddition = {
      tempId: `${cand.employee_id}-${Date.now()}-${Math.random().toString(36).substring(2, 7)}`,
      employee_id: cand.employee_id,
      employee_name: cand.name,
      tally_id: cand.tally_id,
      staff_grade_description: cand.staff_grade_description || undefined,
      assigned_hours: defaultHours,
      override_reason: defaultReason,
      original_employee_id: replacementTargetId || undefined,
      original_employee_name: targetWorker?.employee_name || undefined,
      source: isReplacement ? "OVERRIDE" : "DIRECT",
      is_rest_day: isSameWeekday(cand.weekly_off_day, selectedCell?.cell.weekday || ""),
    };

    setStagedAdditions((prev) => [...prev, newAddition]);
    if (isReplacement) {
      setReplacementTargetId(null);
    }
  };

  // Remove a staged addition
  const handleRemoveStagedAddition = (tempId: string) => {
    setStagedAdditions((prev) => prev.filter((a) => a.tempId !== tempId));
  };

  // Update hours for a staged addition
  const handleUpdateStagedHours = (tempId: string, hours: number) => {
    setStagedAdditions((prev) =>
      prev.map((a) => (a.tempId === tempId ? { ...a, assigned_hours: hours } : a))
    );
  };

  // Update reason for a staged addition
  const handleUpdateStagedReason = (tempId: string, reason: string) => {
    setStagedAdditions((prev) =>
      prev.map((a) => (a.tempId === tempId ? { ...a, override_reason: reason } : a))
    );
  };

  // Cancel and discard modal without API mutations
  const handleCancelModal = () => {
    setSelectedCell(null);
    setStagedRemovals(new Set());
    setStagedAdditions([]);
    setStagedBaseRemovals(new Map());
    setRemovingBaseWorkerId(null);
    setBaseRemovalReasonInput("");
    setReplacementTargetId(null);
  };

  // Atomically save all staged operations
  const handleSaveOperationalRoster = async () => {
    if (!selectedCell) return;
    setSavingShift(true);
    try {
      // 1. Process staged removals (includes deletions of shifts, covers, or restorations of cancelled base workers)
      for (const shiftId of stagedRemovals) {
        const res = await fetch(`/api/v1/operational-planner/shifts/${shiftId}`, {
          method: "DELETE",
          headers: { Authorization: `Bearer ${token}` },
        });
        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.detail || "Failed to remove shift");
        }
      }

      // 2. Process staged base removals (creates CANCELLED shift record with override_reason)
      for (const baseRemoval of Array.from(stagedBaseRemovals.values())) {
        const payload: OperationalShiftCreate = {
          job_item_id: selectedCell.item.job_item_id,
          work_date: selectedCell.cell.work_date,
          employee_id: baseRemoval.employee_id,
          assigned_hours: baseRemoval.assigned_hours,
          override_reason: baseRemoval.reason,
          source: "OVERRIDE",
          status: "CANCELLED",
          acknowledge_warnings: true,
        };

        const res = await fetch("/api/v1/operational-planner/shifts", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.detail || "Failed to remove base shift");
        }
      }

      // 3. Process staged additions
      for (const addition of stagedAdditions) {
        const payload: OperationalShiftCreate = {
          job_item_id: selectedCell.item.job_item_id,
          work_date: selectedCell.cell.work_date,
          employee_id: addition.employee_id,
          original_employee_id: addition.original_employee_id || undefined,
          assigned_hours: addition.assigned_hours,
          override_reason: addition.override_reason || (addition.source === "OVERRIDE" ? "Leave Cover" : "Additional shift"),
          source: addition.source,
          status: "ACTIVE",
          acknowledge_warnings: true,
        };

        const res = await fetch("/api/v1/operational-planner/shifts", {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Authorization: `Bearer ${token}`,
          },
          body: JSON.stringify(payload),
        });

        if (!res.ok) {
          const errJson = await res.json().catch(() => ({}));
          throw new Error(errJson.detail || "Failed to assign operational shift");
        }
      }

      const scrollPos = window.scrollY;
      await fetchOperationalData(true);
      handleCancelModal();
      setTimeout(() => {
        window.scrollTo({ top: scrollPos, behavior: "instant" });
      }, 0);
    } catch (err: any) {
      alert(`Error saving operational roster: ${err.message}`);
    } finally {
      setSavingShift(false);
    }
  };

  // Filter and sort worksites in Coverage View (pinned worksites at top)
  const sortedAndFilteredCoverageWorksites = useMemo(() => {
    if (!coverageData) return [];
    const q = searchQuery.toLowerCase().trim();
    let list = coverageData.worksites;
    if (q) {
      list = list.filter(
        (ws) =>
          ws.job_number.toLowerCase().includes(q) ||
          ws.job_name.toLowerCase().includes(q) ||
          (ws.customer_type && ws.customer_type.toLowerCase().includes(q))
      );
    }
    return [...list].sort((a, b) => {
      const aPinned = pinnedWorksites.has(a.worksite_id);
      const bPinned = pinnedWorksites.has(b.worksite_id);
      if (aPinned !== bPinned) return aPinned ? -1 : 1;
      return a.job_number.localeCompare(b.job_number);
    });
  }, [coverageData, searchQuery, pinnedWorksites]);

  // Unique job numbers for Worker Roster filter dropdown
  const availableJobNumbers = useMemo(() => {
    if (!rosterData) return [];
    const set = new Set<string>();
    for (const w of rosterData.workers) {
      for (const jn of w.assigned_job_numbers || []) {
        if (jn) set.add(jn);
      }
    }
    return Array.from(set).sort();
  }, [rosterData]);

  // Filter and sort workers in Worker Roster View (pinned workers at top)
  const filteredAndSortedWorkers = useMemo(() => {
    if (!rosterData) return [];
    let list = rosterData.workers;

    // 1. Search Query
    const q = rosterSearchQuery.toLowerCase().trim();
    if (q) {
      list = list.filter(
        (w) =>
          w.name.toLowerCase().includes(q) ||
          w.tally_id.toLowerCase().includes(q) ||
          (w.staff_grade_description && w.staff_grade_description.toLowerCase().includes(q)) ||
          (w.assigned_job_numbers && w.assigned_job_numbers.some((jn) => jn.toLowerCase().includes(q)))
      );
    }

    // 2. Job Filter
    if (selectedJobFilter) {
      list = list.filter(
        (w) => w.assigned_job_numbers && w.assigned_job_numbers.includes(selectedJobFilter)
      );
    }

    // 3. Supervisor Crew Filter (if selected in top header)
    if (selectedSupervisorId) {
      list = list.filter((w) => w.supervisor_id === selectedSupervisorId);
    }

    // 4. Sort pinned to top, then alphabetical
    return [...list].sort((a, b) => {
      const aPinned = pinnedWorkers.has(a.employee_id);
      const bPinned = pinnedWorkers.has(b.employee_id);
      if (aPinned !== bPinned) return aPinned ? -1 : 1;
      return a.name.localeCompare(b.name);
    });
  }, [rosterData, rosterSearchQuery, selectedJobFilter, selectedSupervisorId, pinnedWorkers]);

  // Supervisor groups when Group by Supervisor is enabled
  const supervisorGroups = useMemo(() => {
    if (!groupBySupervisor || !filteredAndSortedWorkers.length) return null;
    const map = new Map<
      string,
      {
        supervisor_id: string | null;
        supervisor_name: string;
        workers: OperationalRosterWorkerRow[];
        totalHours: number;
      }
    >();

    for (const w of filteredAndSortedWorkers) {
      const key = w.supervisor_id || "unassigned";
      const name = w.supervisor_name || "Unassigned Crew";
      if (!map.has(key)) {
        map.set(key, {
          supervisor_id: w.supervisor_id || null,
          supervisor_name: name,
          workers: [],
          totalHours: 0,
        });
      }
      const group = map.get(key)!;
      group.workers.push(w);
      group.totalHours += Number(w.total_week_hours) || 0;
    }

    return Array.from(map.values()).sort((a, b) =>
      a.supervisor_name.localeCompare(b.supervisor_name)
    );
  }, [filteredAndSortedWorkers, groupBySupervisor]);

  // Filter candidates in modal
  const filteredCandidates = useMemo(() => {
    let pool = candidates;

    // 1. Exclude the worker being replaced/covered
    if (replacementTargetId) {
      pool = pool.filter((c) => c.employee_id !== replacementTargetId);
    }

    // 2. Exclude workers already active/assigned in this cell (unless staged for removal or already removed)
    if (selectedCell) {
      const activeAssignedIds = new Set(
        selectedCell.cell.workers
          .filter(
            (w) =>
              w.display_type !== "REMOVED" &&
              (!w.shift_id || !stagedRemovals.has(w.shift_id)) &&
              !stagedBaseRemovals.has(w.employee_id)
          )
          .map((w) => w.employee_id)
      );
      const stagedIds = new Set(stagedAdditions.map((a) => a.employee_id));
      pool = pool.filter((c) => !activeAssignedIds.has(c.employee_id) && !stagedIds.has(c.employee_id));
    }

    if (filterToSupervisorCrew && selectedSupervisorId) {
      pool = pool.filter((c) => c.supervisor_id === selectedSupervisorId);
    }

    const q = candidateSearch.toLowerCase().trim();
    if (q) {
      pool = pool.filter(
        (c) =>
          c.name.toLowerCase().includes(q) ||
          c.tally_id.toLowerCase().includes(q) ||
          (c.staff_grade_description && c.staff_grade_description.toLowerCase().includes(q))
      );
    }

    return [...pool].sort((a, b) => {
      // Unblocked candidates always rank before blocked candidates
      if (Boolean(a.is_blocked) !== Boolean(b.is_blocked)) {
        return a.is_blocked ? 1 : -1;
      }
      if (a.exact_staff_type_match !== b.exact_staff_type_match) {
        return a.exact_staff_type_match ? -1 : 1;
      }
      return (b.ranking_score || 0) - (a.ranking_score || 0);
    });
  }, [
    candidates,
    candidateSearch,
    filterToSupervisorCrew,
    selectedSupervisorId,
    replacementTargetId,
    selectedCell,
    stagedRemovals,
    stagedBaseRemovals,
    stagedAdditions,
  ]);

  // Render a worker row in the Worker Roster table
  const renderWorkerRow = (w: OperationalRosterWorkerRow) => {
    const isWorkerPinned = pinnedWorkers.has(w.employee_id);
    const totalHours = Number(w.total_week_hours) || 0;
    const standardHours = Number(w.standard_week_hours) || 0;
    const isOvertime = totalHours > standardHours;
    const isTargetMet = totalHours === standardHours;
    const otHours = (totalHours - standardHours).toFixed(1);
    const underHours = (standardHours - totalHours).toFixed(1);

    return (
      <tr key={w.employee_id} className="hover:bg-slate-50/50 transition-colors">
        <td className="px-4 py-3">
          <div className="flex items-center justify-between gap-2">
            <div className="font-bold text-slate-900 flex items-center gap-1.5 min-w-0">
              <button
                type="button"
                onClick={() => togglePinWorker(w.employee_id)}
                className={`p-1 rounded transition-colors ${
                  isWorkerPinned
                    ? "text-amber-500 hover:text-amber-600"
                    : "text-slate-300 hover:text-slate-500"
                }`}
                title={isWorkerPinned ? "Unpin worker" : "Pin worker to top"}
              >
                <Pin className={`h-3.5 w-3.5 ${isWorkerPinned ? "fill-amber-400 text-amber-500" : ""}`} />
              </button>
              <span className="truncate">{w.name}</span>
              <span className="font-mono text-[10px] text-slate-400 shrink-0">({w.tally_id})</span>
            </div>

            {/* Weekly Total Badge with Heatmap */}
            {isOvertime ? (
              <span className="font-bold text-purple-700 bg-purple-50 border border-purple-200 px-2 py-0.5 rounded text-[10px] shrink-0">
                {totalHours} / {standardHours}h (+{otHours}h OT)
              </span>
            ) : isTargetMet ? (
              <span className="font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded text-[10px] shrink-0">
                {totalHours} / {standardHours}h (Met)
              </span>
            ) : (
              <span className="font-semibold text-amber-700 bg-amber-50 border border-amber-200 px-2 py-0.5 rounded text-[10px] shrink-0">
                {totalHours} / {standardHours}h ({underHours}h Under)
              </span>
            )}
          </div>

          <div className="text-[11px] text-slate-500 mt-0.5 flex flex-wrap items-center gap-2 pl-6">
            <span>{w.staff_grade_description || "Worker"}</span>
            {w.supervisor_name && (
              <>
                <span>•</span>
                <span className="text-slate-400">Crew: {w.supervisor_name}</span>
              </>
            )}
          </div>
        </td>

        {w.days.map((d) => (
          <td
            key={d.work_date}
            className={`px-2 py-2 border-l border-slate-200 text-center ${
              d.is_weekly_off ? "bg-slate-50 text-slate-400" : ""
            }`}
          >
            {d.is_weekly_off ? (
              <span className="text-[10px] font-semibold px-2 py-0.5 rounded bg-slate-200 text-slate-600">
                WEEKLY OFF
              </span>
            ) : d.shifts.length > 0 ? (
              <div className="space-y-1">
                {d.shifts.map((s, idx) => {
                  const isRemoved = s.opacity_class === "removed";
                  const hours = Number(s.assigned_hours) || 0;
                  const isDailyOT = hours > 8;
                  const isDailyMet = hours === 8;

                  if (isRemoved) {
                    return (
                      <div
                        key={idx}
                        className="p-1 rounded text-[10px] font-medium bg-rose-50 text-rose-700 border border-dashed border-rose-300 line-through"
                        title={s.reason ? `Removed: ${s.reason}` : "Shift Cancelled"}
                      >
                        {hours}h (Removed)
                      </div>
                    );
                  }

                  return (
                    <div
                      key={idx}
                      className={`p-1 rounded text-[10px] font-semibold ${
                        isDailyOT
                          ? "bg-purple-600 text-white shadow-sm"
                          : isDailyMet
                          ? "bg-indigo-600 text-white shadow-sm"
                          : "bg-sky-100 text-sky-900 border border-sky-300"
                      }`}
                      title={s.reason || undefined}
                    >
                      {hours}h Shift {isDailyOT && `(+${(hours - 8).toFixed(1)}h OT)`}
                    </div>
                  );
                })}
              </div>
            ) : (
              <span className="text-slate-300 text-[10px]">—</span>
            )}
          </td>
        ))}
      </tr>
    );
  };

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Top Controls Bar - Light Enterprise Styling */}
      <header className="bg-white border-b border-slate-200 px-6 py-4 sticky top-0 z-20">
        <div className="flex flex-col lg:flex-row lg:items-center justify-between gap-4">
          <div>
            <div className="flex items-center gap-2">
              <CalendarDays className="h-6 w-6 text-indigo-600" />
              <h1 className="text-xl font-bold text-slate-900">
                Operational Planner (Live Daily Schedule)
              </h1>
              <span className="px-2.5 py-0.5 rounded-full text-xs font-semibold bg-emerald-50 text-emerald-700 border border-emerald-200">
                Live Operations
              </span>
              {isRefreshing && (
                <span className="text-xs text-indigo-600 flex items-center gap-1 font-medium bg-indigo-50/80 px-2 py-0.5 rounded border border-indigo-200 animate-pulse">
                  <Loader2 className="h-3 w-3 animate-spin" /> Saving & updating...
                </span>
              )}
            </div>
            <p className="text-sm text-slate-500 mt-1">
              Active shifts, leave covers, base shift removals and operational adjustments.
            </p>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            {/* Lens Switcher */}
            <div className="bg-slate-100 p-1 rounded-lg flex items-center text-xs font-semibold">
              <button
                type="button"
                onClick={() => setActiveLens("COVERAGE")}
                className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                  activeLens === "COVERAGE"
                    ? "bg-white text-indigo-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Building2 className="h-3.5 w-3.5" />
                Coverage View (Jobs)
              </button>
              <button
                type="button"
                onClick={() => setActiveLens("ROSTER")}
                className={`px-3 py-1.5 rounded-md transition-all flex items-center gap-1.5 ${
                  activeLens === "ROSTER"
                    ? "bg-white text-indigo-700 shadow-sm"
                    : "text-slate-600 hover:text-slate-900"
                }`}
              >
                <Users className="h-3.5 w-3.5" />
                Worker Roster
              </button>
            </div>

            {/* Supervisor Crew Filter Dropdown */}
            <div className="flex items-center gap-2 bg-white border border-slate-200 rounded-lg px-3 py-1.5 shadow-sm">
              <UserCheck className="h-4 w-4 text-slate-400" />
              <span className="text-xs font-semibold text-slate-700">Supervisor Crew:</span>
              <select
                value={selectedSupervisorId}
                onChange={(e) => setSelectedSupervisorId(e.target.value)}
                className="text-xs bg-transparent border-0 font-medium text-slate-800 focus:outline-none cursor-pointer"
              >
                <option value="">All Crews (Company-Wide)</option>
                {supervisorsList.map((sup) => (
                  <option key={sup.id} value={sup.id}>
                    {sup.name} ({sup.tally_id || "Crew"})
                  </option>
                ))}
              </select>
            </div>

            {/* Week Navigator */}
            <div className="flex items-center gap-1 bg-white border border-slate-200 rounded-lg p-1 shadow-sm">
              <button
                onClick={handlePrevWeek}
                title="Previous Week"
                className="p-1 rounded hover:bg-slate-100 text-slate-600"
              >
                <ChevronLeft className="h-4 w-4" />
              </button>
              <span className="font-semibold text-xs px-2 text-slate-800">
                {formatReadableWeek(weekStartDate)}
              </span>
              <button
                onClick={handleNextWeek}
                title="Next Week"
                className="p-1 rounded hover:bg-slate-100 text-slate-600"
              >
                <ChevronRight className="h-4 w-4" />
              </button>
              <button
                onClick={handleCurrentWeek}
                className="ml-1 text-[11px] font-bold px-2 py-0.5 rounded bg-slate-100 text-slate-700 hover:bg-slate-200"
              >
                Current Week
              </button>
            </div>

            {/* Worksite Search (Coverage View) */}
            {activeLens === "COVERAGE" && (
              <div className="relative w-56">
                <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
                <input
                  type="text"
                  placeholder="Search worksite..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
                />
              </div>
            )}

            {/* Reassignments History Toggle Button */}
            <button
              type="button"
              onClick={() => setShowReassignmentsHistory(!showReassignmentsHistory)}
              className={`px-3 py-1.5 rounded-lg text-xs font-semibold border transition flex items-center gap-1.5 cursor-pointer ${
                showReassignmentsHistory
                  ? "bg-purple-100 text-purple-800 border-purple-300"
                  : "bg-white text-slate-700 hover:bg-slate-50 border-slate-200 shadow-2xs"
              }`}
              title="View recent temporary reassignments and audit history"
            >
              <Clock className="h-3.5 w-3.5 text-purple-600" />
              Reassignments ({recentReassignments.length})
            </button>

            {/* Request Reassignment Action Button */}
            <button
              type="button"
              onClick={() => {
                setReassignError(null);
                setReassignSuccess(null);
                setReassignPreview(null);
                setReassignmentModalOpen(true);
              }}
              className="px-3.5 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 text-white flex items-center gap-1.5 shadow-sm transition cursor-pointer"
            >
              <Plus className="h-3.5 w-3.5" />
              Request Reassignment
            </button>
          </div>
        </div>

        {/* Legend */}
        <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 mt-3 pt-3 border-t border-slate-100">
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-50 border border-dashed border-indigo-400 opacity-60"></span>
            <span>Base Blueprint (Muted)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-indigo-600 shadow-sm"></span>
            <span className="font-semibold text-slate-700">Operational Override / Cover (Solid)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-rose-50 border border-dashed border-rose-400"></span>
            <span className="text-rose-700 font-semibold line-through">Removed Base Shift</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="w-3 h-3 rounded bg-amber-50 border border-dashed border-amber-400"></span>
            <span className="text-amber-700 font-semibold">TO_BE_COVERED (Leave Gap)</span>
          </div>
          <div className="flex items-center gap-1.5">
            <CheckCircle2 className="h-3.5 w-3.5 text-emerald-600" />
            <span className="text-emerald-700 font-medium">Quota Met</span>
          </div>
          <div className="flex items-center gap-1.5">
            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-purple-100 text-purple-700">Excess</span>
            <span>Excess Visit</span>
          </div>
        </div>
      </header>

      {/* Reassignments History Tray */}
      {showReassignmentsHistory && (
        <div className="bg-purple-50/80 border-b border-purple-200 px-6 py-3 shadow-2xs space-y-2">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold text-purple-900 flex items-center gap-1.5">
              <Clock className="h-4 w-4 text-purple-600" />
              Temporary Operational Reassignments ({recentReassignments.length})
            </span>
            <button
              onClick={() => setShowReassignmentsHistory(false)}
              className="text-xs text-purple-700 hover:text-purple-900 font-semibold cursor-pointer"
            >
              ✕ Close
            </button>
          </div>
          {recentReassignments.length === 0 ? (
            <p className="text-xs text-purple-700 italic">No temporary reassignments on record.</p>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-2.5 max-h-56 overflow-y-auto pt-1">
              {recentReassignments.map((r: any) => (
                <div
                  key={r.id}
                  className="p-2.5 bg-white rounded-lg border border-purple-200 shadow-2xs text-xs space-y-1 flex flex-col justify-between"
                >
                  <div>
                    <div className="flex items-center justify-between gap-1">
                      <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-purple-100 text-purple-800">
                        {r.reassignment_type}
                      </span>
                      <span
                        className={`px-1.5 py-0.2 rounded-full text-[10px] font-bold ${
                          r.status === "APPROVED"
                            ? "bg-emerald-100 text-emerald-800"
                            : r.status === "PENDING"
                            ? "bg-amber-100 text-amber-800"
                            : "bg-rose-100 text-rose-800"
                        }`}
                      >
                        {r.status}
                      </span>
                    </div>
                    <div className="font-semibold text-slate-800 mt-1">
                      {r.reassignment_type === "REPLACE"
                        ? `${r.original_employee_name} → ${r.new_employee_name}`
                        : r.new_employee_name || r.original_employee_name}
                    </div>
                    <div className="text-[11px] text-slate-500">
                      {r.date_from === r.date_to ? r.date_from : `${r.date_from} to ${r.date_to}`}
                      {r.target_job_name && ` · ${r.target_job_name}`}
                    </div>
                    <div className="text-[10px] text-slate-400">
                      Req by: {r.requested_by_name || "Supervisor"}
                      {r.decided_by_name && ` · Decided: ${r.decided_by_name}`}
                    </div>
                  </div>
                  <button
                    onClick={() => handleFocusReassignment(r)}
                    className="mt-1 w-full py-1 bg-purple-50 hover:bg-purple-100 text-purple-700 font-bold rounded text-[11px] border border-purple-200 transition cursor-pointer"
                  >
                    Focus in Planner
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Staffing Gaps / Uncovered Leave Shortages Banner */}
      {staffingGaps.length > 0 && (
        <div className="bg-amber-50 border-b border-amber-200 px-6 py-2.5 flex flex-wrap items-center justify-between gap-3 shadow-2xs">
          <div className="flex items-center gap-2.5">
            <div className="p-1.5 bg-amber-100 rounded-full text-amber-700">
              <AlertTriangle className="h-4 w-4" />
            </div>
            <div>
              <span className="font-bold text-xs text-amber-950">
                {staffingGaps.length} Leave Shift{staffingGaps.length > 1 ? "s" : ""} Requiring Cover:
              </span>
              <div className="flex flex-wrap items-center gap-2 mt-1">
                {staffingGaps.slice(0, 4).map((gap, idx) => (
                  <span
                    key={idx}
                    className="inline-flex items-center gap-1.5 bg-white px-2 py-0.5 rounded border border-amber-300 text-slate-800 text-xs shadow-2xs"
                  >
                    <span className="font-semibold text-slate-900">{gap.original_employee_name}</span>
                    <span className="text-2xs text-slate-500">
                      {gap.work_date} • {gap.job_number}
                    </span>
                    <button
                      type="button"
                      onClick={() => handleOpenReassignmentForGap(gap)}
                      className="text-xs font-bold text-indigo-700 hover:text-indigo-900 ml-1 underline cursor-pointer"
                    >
                      Assign
                    </button>
                  </span>
                ))}
                {staffingGaps.length > 4 && (
                  <span className="text-xs font-semibold text-amber-800">
                    +{staffingGaps.length - 4} more
                  </span>
                )}
              </div>
            </div>
          </div>
          <button
            type="button"
            onClick={() => {
              if (staffingGaps.length > 0) handleOpenReassignmentForGap(staffingGaps[0]);
              else setReassignmentModalOpen(true);
            }}
            className="px-3 py-1.5 bg-amber-700 hover:bg-amber-800 text-white font-semibold rounded-md text-xs transition shadow-2xs flex items-center gap-1 cursor-pointer"
          >
            <Users className="h-3.5 w-3.5" />
            Assign Cover for Gap
          </button>
        </div>
      )}

      {/* Request Temporary Reassignment Modal (D2, BR-SC-04) */}
      {reassignmentModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-xl max-h-[92vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Users className="h-5 w-5 text-indigo-600" />
                  Request Temporary Reassignment
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Operational adjustment for specific dates (requires ≥ 3 days notice per company policy).
                </p>
              </div>
              <button
                type="button"
                onClick={() => setReassignmentModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body / Form */}
            <form onSubmit={handleCreateReassignment} className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* Type Switcher */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Reassignment Type
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {(["REPLACE", "MOVE", "ADD", "CANCEL"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => {
                        setReassignType(t);
                        setReassignError(null);
                        setReassignPreview(null);
                      }}
                      className={`py-2 px-2.5 rounded-lg text-xs font-bold text-center border transition cursor-pointer ${
                        reassignType === t
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-xs"
                          : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <p className="text-2xs text-slate-500 mt-1.5">
                  {reassignType === "REPLACE" && "Assign a replacement worker to cover an absent worker's shift."}
                  {reassignType === "MOVE" && "Relocate a worker from their blueprint site to another job site."}
                  {reassignType === "ADD" && "Deploy an additional worker to a job site for operational need."}
                  {reassignType === "CANCEL" && "Cancel a scheduled shift due to client closure or weather conditions."}
                </p>
              </div>

              {/* Date Selectors & Notice Period Banner */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Date From <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={reassignDateFrom}
                    onChange={(e) => setReassignDateFrom(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Date To <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={reassignDateTo}
                    onChange={(e) => setReassignDateTo(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  />
                </div>
              </div>

              {/* Notice Validation Banner */}
              <div
                className={`p-3 rounded-lg border text-xs flex items-center justify-between gap-2 ${
                  noticeDays >= 3
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-800"
                }`}
              >
                <div className="flex items-center gap-2">
                  {noticeDays >= 3 ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
                  )}
                  <span>
                    {noticeDays >= 3
                      ? `${noticeDays} days advance notice (Valid notice period per BR-SC-04)`
                      : `Notice is ${noticeDays} day(s). System requires strictly ≥ 3 days notice.`}
                  </span>
                </div>
                <span className="text-2xs font-extrabold uppercase tracking-wide">
                  {noticeDays >= 3 ? "Allowed" : user?.role === "ADMIN" ? "Admin Override" : "Refused"}
                </span>
              </div>

              {/* Original Worker (REPLACE, MOVE, CANCEL) */}
              {(reassignType === "REPLACE" || reassignType === "MOVE" || reassignType === "CANCEL") && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Original Worker (Absent / Being Moved) <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={reassignOrigEmpId}
                    onChange={(e) => setReassignOrigEmpId(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="">-- Select Worker --</option>
                    {availableEmployees.map((emp: any) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name || emp.employee_name} ({emp.tally_id || "No Tally"} • {emp.staff_grade_description || emp.role || "Worker"})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Target Worksite & Job Item (REPLACE, MOVE, ADD) */}
              {(reassignType === "REPLACE" || reassignType === "MOVE" || reassignType === "ADD") && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Target Worksite & Job Item <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={reassignJobItemId}
                    onChange={(e) => setReassignJobItemId(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="">-- Select Target Job Item --</option>
                    {availableJobItems.map((j) => (
                      <option key={j.job_item_id} value={j.job_item_id}>
                        {j.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Replacement / New Worker (REPLACE, ADD) */}
              {(reassignType === "REPLACE" || reassignType === "ADD") && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-semibold text-slate-700">
                      Replacement / New Worker <span className="text-rose-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={handlePreviewReassignment}
                      disabled={previewLoading || !reassignNewEmpId}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                    >
                      {previewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                      Preview Worker Hours
                    </button>
                  </div>
                  <select
                    value={reassignNewEmpId}
                    onChange={(e) => setReassignNewEmpId(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="">-- Select Replacement Worker --</option>
                    {availableEmployees.map((emp: any) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name || emp.employee_name} ({emp.tally_id || "No Tally"} • {emp.staff_grade_description || emp.role || "Worker"})
                      </option>
                    ))}
                  </select>

                  {/* Preview Result Card */}
                  {reassignPreview && (
                    <div className="mt-2.5 p-3 rounded-lg bg-indigo-50/70 border border-indigo-200 text-xs space-y-1">
                      <div className="font-bold text-indigo-900 flex items-center justify-between">
                        <span>Projected Total Weekly Hours: {reassignPreview.total_weekly_hours}h</span>
                        {reassignPreview.planned_overtime_hours > 0 && (
                          <span className="text-amber-700 font-bold">
                            OT: +{reassignPreview.planned_overtime_hours}h
                          </span>
                        )}
                      </div>
                      {reassignPreview.warnings?.length > 0 ? (
                        <div className="text-rose-700 space-y-0.5 pt-1">
                          {reassignPreview.warnings.map((w: string, idx: number) => (
                            <div key={idx} className="flex items-center gap-1">
                              <AlertCircle className="h-3 w-3 shrink-0" />
                              <span>{w}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-2xs text-emerald-700 font-medium">
                          ✓ No schedule conflicts or overtime violations detected.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Reason Category & Reason */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Reason Category <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={reassignReasonCategory}
                    onChange={(e) => setReassignReasonCategory(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="LEAVE_COVER">Leave Cover Absence</option>
                    <option value="CAPACITY">Operational Capacity Shortfall</option>
                    <option value="WEATHER">Weather Conditions</option>
                    <option value="PRIORITY">High-Priority Client Request</option>
                    <option value="OTHER">Other Operational Need</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Reason Details <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Covering sick leave for gardener..."
                    value={reassignReason}
                    onChange={(e) => setReassignReason(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  />
                </div>
              </div>

              {/* Errors & Success Banners */}
              {reassignError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-lg flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{reassignError}</span>
                </div>
              )}
              {reassignSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{reassignSuccess}</span>
                </div>
              )}

              {/* Modal Footer Actions */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-2xs text-slate-400">
                  Engineer or Admin approval required before operational schedule is updated.
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setReassignmentModalOpen(false)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100 transition cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={reassignSubmitting || (noticeDays < 3 && user?.role !== "ADMIN")}
                    className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white flex items-center gap-1.5 shadow-xs transition cursor-pointer"
                  >
                    {reassignSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Submit Reassignment Request
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}

      {/* Main Grid Content */}
      <main className="flex-1 overflow-auto p-6 space-y-6">
        {loading ? (
          <div className="flex flex-col items-center justify-center h-64 text-slate-400">
            <Loader2 className="h-8 w-8 animate-spin mb-2" />
            <p className="text-sm font-medium">Loading Operational Schedule...</p>
          </div>
        ) : error ? (
          <div className="p-4 rounded-lg bg-red-50 text-red-700 border border-red-200 text-sm">
            {error}
          </div>
        ) : activeLens === "COVERAGE" && coverageData ? (
          /* Coverage Matrix View */
          <div className="space-y-6">
            {sortedAndFilteredCoverageWorksites.map((ws) => {
              const isPinned = pinnedWorksites.has(ws.worksite_id);

              return (
                <div
                  key={ws.worksite_id}
                  className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden"
                >
                  {/* Worksite Banner Bar */}
                  <div className="px-6 py-3.5 bg-slate-50 border-b border-slate-200 flex flex-col md:flex-row md:items-center justify-between gap-3">
                    <div className="space-y-0.5">
                      <div className="flex items-center gap-2.5">
                        <button
                          type="button"
                          onClick={() => togglePinWorksite(ws.worksite_id)}
                          className={`p-1 rounded-lg border transition-colors ${
                            isPinned
                              ? "bg-amber-50 border-amber-300 text-amber-600 hover:bg-amber-100"
                              : "bg-white border-slate-200 text-slate-400 hover:text-slate-600 hover:bg-slate-50"
                          }`}
                          title={isPinned ? "Unpin worksite" : "Pin worksite to top"}
                        >
                          <Pin className={`h-3.5 w-3.5 ${isPinned ? "fill-amber-400 text-amber-500" : ""}`} />
                        </button>
                        <span className="font-mono text-sm font-bold text-indigo-600">
                          {ws.job_number}
                        </span>
                        <h2 className="text-sm font-bold text-slate-900">
                          {ws.job_name}
                        </h2>
                        {ws.customer_type && (
                          <span className="text-[10px] px-2 py-0.5 rounded bg-slate-200 text-slate-700 font-medium">
                            {ws.customer_type}
                          </span>
                        )}
                        <span
                          className={`text-[10px] px-2 py-0.5 rounded font-medium ${
                            ws.is_outdoor
                              ? "bg-amber-100 text-amber-800"
                              : "bg-blue-100 text-blue-800"
                          }`}
                        >
                          {ws.is_outdoor ? "Outdoor Site" : "Indoor Site"}
                        </span>
                      </div>

                      <div className="flex flex-wrap items-center gap-4 text-xs text-slate-500 pt-0.5 pl-6">
                        <div>
                          <span className="font-medium text-slate-700">Contract Validity:</span>{" "}
                          {ws.start_date || "N/A"} to {ws.end_date || "Ongoing"}
                        </div>
                        <div>
                          <span className="font-medium text-slate-700">Annual Budget:</span>{" "}
                          {ws.budget_amount ? `${Number(ws.budget_amount).toLocaleString()} AED / yr` : "Not specified"}
                        </div>
                        <div>
                          <span className="font-medium text-slate-700">Items:</span> {ws.items.length} contract lines
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* 7-Day Coverage Table */}
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs border-collapse">
                      <thead>
                        <tr className="bg-slate-100/70 text-slate-500 border-b border-slate-200">
                          <th className="px-4 py-2.5 font-semibold w-72">Job Item & Quota</th>
                          {ws.items[0]?.days.map((d) => (
                            <th
                              key={d.work_date}
                              className={`px-3 py-2 text-center border-l border-slate-200 min-w-[130px] ${
                                d.is_public_holiday ? "bg-sky-50" : ""
                              }`}
                            >
                              <div className="font-bold text-slate-800">{d.weekday}</div>
                              <div className="text-[10px] text-slate-400">{d.work_date.slice(5)}</div>
                              {d.is_public_holiday && (
                                <div
                                  className="text-[9px] font-bold text-sky-800 truncate max-w-[120px] mx-auto mt-0.5 bg-sky-100/80 px-1 py-0.2 rounded border border-sky-200"
                                  title={d.holiday_name || "Public Holiday"}
                                >
                                  {d.holiday_name || "Holiday"}
                                </div>
                              )}
                            </th>
                          ))}
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-slate-100">
                        {ws.items.map((it) => (
                          <tr
                            key={it.job_item_id}
                            className={`transition-colors ${
                              highlightedJobItemId === it.job_item_id
                                ? "bg-indigo-50/90 ring-2 ring-indigo-500 shadow-xs"
                                : "hover:bg-slate-50/50"
                            }`}
                          >
                            {/* Item Info Column */}
                            <td className="px-4 py-3">
                              <div className="font-semibold text-slate-900 flex items-center gap-1.5">
                                <span className="font-mono text-indigo-600">{it.sub_item_code}</span>
                                <span>{it.staff_grade_description}</span>
                              </div>
                              <div className="text-[11px] text-slate-500 mt-0.5">
                                Quota: {it.quota_assigned} / {it.quota_target} {it.frequency_unit.toLowerCase()} visits
                              </div>
                              <div className="flex items-center gap-1.5 mt-1">
                                {it.quota_satisfied && (
                                  <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-700 bg-emerald-50 px-1.5 py-0.2 rounded border border-emerald-200">
                                    <CheckCircle2 className="h-3 w-3" /> Quota Met
                                  </span>
                                )}
                                <span className="text-[10px] text-slate-400">
                                  {it.required_staff_count} staff • {it.hours_per_occurrence}h/visit
                                </span>
                              </div>
                            </td>

                            {/* 7 Daily Cells */}
                            {it.days.map((cell) => {
                              const isExcess = cell.is_excess;
                              const hasCoverIssue = cell.is_to_be_covered;

                              return (
                                <td
                                  key={cell.work_date}
                                  onClick={() => handleCellClick(ws, it, cell)}
                                  className={`px-2 py-2 border-l border-slate-200 cursor-pointer transition-colors relative hover:bg-indigo-50/60 ${
                                    cell.is_public_holiday ? "bg-sky-50/40" : ""
                                  }`}
                                >
                                  <div className="space-y-1 min-h-[52px] flex flex-col justify-between">
                                    {/* Badges top */}
                                    <div className="flex items-center justify-between gap-1 text-[9px]">
                                      {isExcess && (
                                        <span className="font-bold px-1.5 py-0.2 rounded bg-purple-100 text-purple-700">
                                          Excess
                                        </span>
                                      )}
                                      {cell.is_quota_met && (
                                        <CheckCircle2 className="h-3 w-3 text-emerald-600 ml-auto" />
                                      )}
                                    </div>

                                    {/* Workers List */}
                                    {cell.workers.length > 0 ? (
                                      <div className="space-y-1">
                                        {cell.workers.map((w, idx) => {
                                          const isRemoved = w.opacity_class === "removed" || w.display_type === "REMOVED";
                                          const isWarning = w.opacity_class === "warning";
                                          const isSolid = w.opacity_class === "solid";

                                          if (isRemoved) {
                                            return (
                                              <div
                                                key={idx}
                                                className="p-1 rounded text-[10px] font-medium flex items-center justify-between gap-1 bg-rose-50 text-rose-800 border border-dashed border-rose-300"
                                                title={w.reason ? `${w.employee_name} • Removed: ${w.reason}` : `${w.employee_name} (Cancelled Base Shift)`}
                                              >
                                                <div className="flex items-center gap-1 min-w-0">
                                                  <FileText className="h-2.5 w-2.5 shrink-0 text-rose-500" />
                                                  <span className="line-through truncate max-w-[85px] text-rose-700">
                                                    {w.employee_name}
                                                  </span>
                                                </div>
                                                <span className="text-[8px] bg-rose-700 text-white px-1 rounded uppercase font-bold shrink-0">
                                                  Removed
                                                </span>
                                              </div>
                                            );
                                          }

                                          if (isWarning) {
                                            return (
                                              <div
                                                key={idx}
                                                className="p-1 rounded text-[10px] font-semibold bg-amber-50 text-amber-900 border border-dashed border-amber-400 flex items-center justify-between"
                                              >
                                                <span className="truncate">{w.employee_name}</span>
                                                <AlertTriangle className="h-3 w-3 text-amber-500 shrink-0" />
                                              </div>
                                            );
                                          }

                                          return (
                                            <div
                                              key={idx}
                                              className={`p-1 rounded text-[10px] font-medium flex items-center justify-between gap-1 ${
                                                isSolid
                                                  ? "bg-indigo-600 text-white shadow-sm font-semibold"
                                                  : "bg-indigo-50 text-indigo-900 border border-dashed border-indigo-300 opacity-60"
                                              }`}
                                              title={w.reason ? `${w.employee_name} • Note: ${w.reason}` : w.employee_name}
                                            >
                                              <div className="flex items-center gap-1 min-w-0">
                                                {w.reason && (
                                                  <FileText
                                                    className={`h-2.5 w-2.5 shrink-0 ${
                                                      isSolid ? "text-white/80" : "text-indigo-400"
                                                    }`}
                                                  />
                                                )}
                                                <span className="truncate max-w-[85px]">
                                                  {w.employee_name}
                                                </span>
                                              </div>
                                              {w.display_type === "OVERRIDE" && (
                                                <span className="text-[8px] bg-indigo-800 text-white px-1 rounded uppercase font-bold shrink-0">
                                                  Cover
                                                </span>
                                              )}
                                              {w.display_type === "DIRECT" && (
                                                <span
                                                  className={`text-[8px] px-1 rounded uppercase font-bold text-white shrink-0 ${
                                                    isExcess ? "bg-purple-700" : "bg-emerald-700"
                                                  }`}
                                                >
                                                  {isExcess ? "Excess" : "Additional"}
                                                </span>
                                              )}
                                            </div>
                                          );
                                        })}
                                      </div>
                                    ) : (
                                      <div className="text-[10px] text-slate-300 text-center py-2">—</div>
                                    )}

                                    {/* Bottom status */}
                                    {hasCoverIssue && (
                                      <div className="text-[9px] font-bold text-amber-700 text-center">
                                        Needs Cover
                                      </div>
                                    )}
                                  </div>
                                </td>
                              );
                            })}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              );
            })}
          </div>
        ) : activeLens === "ROSTER" && rosterData ? (
          /* Worker Roster View */
          <div className="bg-white border border-slate-200 rounded-xl shadow-sm overflow-hidden flex flex-col">
            {/* Worker Roster Toolbar */}
            <div className="p-4 bg-slate-50 border-b border-slate-200 flex flex-wrap items-center justify-between gap-3">
              <div className="flex flex-wrap items-center gap-3">
                {/* Search Input */}
                <div className="relative w-64">
                  <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search worker, ID, grade, or site..."
                    value={rosterSearchQuery}
                    onChange={(e) => setRosterSearchQuery(e.target.value)}
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500 shadow-sm"
                  />
                </div>

                {/* Filter by Job / Worksite */}
                <div className="flex items-center gap-1.5 bg-white border border-slate-200 rounded-lg px-2.5 py-1.5 shadow-sm text-xs">
                  <Filter className="h-3.5 w-3.5 text-slate-400" />
                  <span className="font-semibold text-slate-600">Site/Job:</span>
                  <select
                    value={selectedJobFilter}
                    onChange={(e) => setSelectedJobFilter(e.target.value)}
                    className="bg-transparent border-0 font-medium text-slate-800 focus:outline-none cursor-pointer"
                  >
                    <option value="">All Worksites / Jobs</option>
                    {availableJobNumbers.map((jn) => (
                      <option key={jn} value={jn}>
                        Job {jn}
                      </option>
                    ))}
                  </select>
                </div>

                {/* Group by Supervisor Toggle */}
                <button
                  type="button"
                  onClick={() => setGroupBySupervisor(!groupBySupervisor)}
                  className={`px-3 py-1.5 rounded-lg border text-xs font-semibold flex items-center gap-1.5 transition-colors shadow-sm ${
                    groupBySupervisor
                      ? "bg-indigo-50 text-indigo-700 border-indigo-300"
                      : "bg-white text-slate-700 border-slate-200 hover:bg-slate-100"
                  }`}
                >
                  <Users className="h-3.5 w-3.5" />
                  {groupBySupervisor ? "Grouped by Supervisor" : "Group by Supervisor"}
                </button>
              </div>

              {/* Heatmap Legend */}
              <div className="flex items-center gap-3 text-[11px] text-slate-500">
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded bg-sky-100 border border-sky-300"></span>
                  <span>&lt;8h Part</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded bg-indigo-600"></span>
                  <span>8h Met</span>
                </div>
                <div className="flex items-center gap-1">
                  <span className="w-2.5 h-2.5 rounded bg-purple-600"></span>
                  <span>&gt;8h OT</span>
                </div>
              </div>
            </div>

            {/* Persistent Header Table */}
            <div className="overflow-auto max-h-[calc(100vh-250px)]">
              <table className="w-full text-left text-xs border-collapse">
                <thead className="sticky top-0 z-10 bg-slate-100 shadow-sm border-b border-slate-200">
                  <tr className="text-slate-600">
                    <th className="px-4 py-3 font-semibold w-72 bg-slate-100">Worker & Weekly Total</th>
                    {rosterData.workers[0]?.days.map((d) => (
                      <th
                        key={d.work_date}
                        className={`px-3 py-2 text-center border-l border-slate-200 min-w-[120px] bg-slate-100 ${
                          d.is_public_holiday ? "bg-sky-50/80" : ""
                        }`}
                      >
                        <div className="font-bold text-slate-800">{d.weekday}</div>
                        <div className="text-[10px] text-slate-400">{d.work_date.slice(5)}</div>
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {filteredAndSortedWorkers.length === 0 ? (
                    <tr>
                      <td
                        colSpan={1 + (rosterData.workers[0]?.days.length || 7)}
                        className="text-center py-8 text-slate-400 italic"
                      >
                        No workers match the current filters.
                      </td>
                    </tr>
                  ) : groupBySupervisor && supervisorGroups ? (
                    supervisorGroups.map((group) => (
                      <React.Fragment key={`group-${group.supervisor_id || "none"}`}>
                        <tr className="bg-slate-100/90 font-bold border-y border-slate-300">
                          <td
                            colSpan={1 + (rosterData.workers[0]?.days.length || 7)}
                            className="px-4 py-2 text-slate-800"
                          >
                            <div className="flex items-center justify-between">
                              <span className="flex items-center gap-2">
                                <UserCheck className="h-4 w-4 text-indigo-600" />
                                Supervisor: {group.supervisor_name}
                              </span>
                              <span className="text-xs font-medium text-slate-500">
                                {group.workers.length} worker{group.workers.length === 1 ? "" : "s"} • {group.totalHours.toFixed(1)} crew hrs this week
                              </span>
                            </div>
                          </td>
                        </tr>
                        {group.workers.map(renderWorkerRow)}
                      </React.Fragment>
                    ))
                  ) : (
                    filteredAndSortedWorkers.map(renderWorkerRow)
                  )}
                </tbody>
              </table>
            </div>
          </div>
        ) : null}
      </main>

      {/* Single-Action Operational Modal - Light Theme Enterprise */}
      {selectedCell && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-sm">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-xl max-h-[90vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <CalendarDays className="h-5 w-5 text-indigo-600" />
                  Operational Shift Action
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  {selectedCell.cell.weekday} {selectedCell.cell.work_date} • {selectedCell.worksite.job_number} (
                  {selectedCell.item.sub_item_code} - {selectedCell.item.staff_grade_description})
                </p>
              </div>

              <button
                onClick={handleCancelModal}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body */}
            <div className="p-6 space-y-5 flex-1 overflow-y-auto">
              {/* 1. Currently Scheduled Staff in Slot */}
              <div className="space-y-2">
                <div className="flex items-center justify-between">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <Users className="h-4 w-4 text-slate-500" />
                    Currently Scheduled Staff ({selectedCell.cell.workers.length})
                  </h4>
                  {(stagedRemovals.size > 0 || stagedBaseRemovals.size > 0) && (
                    <span className="text-[10px] font-bold text-red-700 bg-red-50 border border-red-200 px-2 py-0.5 rounded">
                      {stagedRemovals.size + stagedBaseRemovals.size} pending removal/restore
                    </span>
                  )}
                </div>

                {selectedCell.cell.workers.length === 0 ? (
                  <p className="text-xs text-slate-400 italic py-1">No workers currently scheduled for this slot.</p>
                ) : (
                  <div className="space-y-2">
                    {selectedCell.cell.workers.map((w, idx) => {
                      const isRemoved = w.display_type === "REMOVED" || w.opacity_class === "removed";
                      const isShiftMarkedForRemoval = w.shift_id ? stagedRemovals.has(w.shift_id) : false;
                      const isBaseStagedForRemoval = stagedBaseRemovals.has(w.employee_id);
                      const stagedBaseInfo = stagedBaseRemovals.get(w.employee_id);

                      // Case A: Already Removed Base Worker (persisted in DB with status CANCELLED)
                      if (isRemoved) {
                        return (
                          <div
                            key={idx}
                            className="p-3 rounded-lg border border-rose-200 bg-rose-50/50 space-y-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold line-through text-rose-700">
                                  {w.employee_name}
                                </span>
                                {w.tally_id && (
                                  <span className="font-mono text-[10px] text-slate-400">({w.tally_id})</span>
                                )}
                                <span className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold bg-rose-700 text-white">
                                  REMOVED
                                </span>
                                {isShiftMarkedForRemoval && (
                                  <span className="text-[9px] font-bold text-emerald-700 bg-emerald-100 px-1.5 py-0.2 rounded border border-emerald-300">
                                    Pending Restoration
                                  </span>
                                )}
                              </div>

                              {isShiftMarkedForRemoval ? (
                                <button
                                  type="button"
                                  onClick={() => handleUndoRemoveShift(w.shift_id!)}
                                  className="px-2 py-1 rounded text-slate-700 hover:bg-slate-200 text-xs font-semibold flex items-center gap-1 border border-slate-300 bg-white"
                                >
                                  <Undo2 className="h-3.5 w-3.5" /> Undo
                                </button>
                              ) : (
                                <button
                                  type="button"
                                  onClick={() => handleStageRemoveShift(w.shift_id!)}
                                  className="px-2.5 py-1 rounded text-emerald-800 bg-white hover:bg-emerald-50 text-xs font-semibold flex items-center gap-1 border border-emerald-300 shadow-xs"
                                  title="Restore recurring base blueprint worker for this date"
                                >
                                  <RotateCcw className="h-3.5 w-3.5 text-emerald-600" /> Restore Base Worker
                                </button>
                              )}
                            </div>

                            <div className="text-[11px] text-rose-800 flex items-center gap-1.5 pt-0.5 font-medium">
                              <FileText className="h-3 w-3 text-rose-500 shrink-0" />
                              <span>Reason: {w.reason || "Shift cancelled"}</span>
                            </div>
                          </div>
                        );
                      }

                      // Case B: Blueprint Base Worker (Recurring from base template, no shift_id yet)
                      if (!w.shift_id) {
                        if (isBaseStagedForRemoval) {
                          return (
                            <div
                              key={idx}
                              className="p-3 rounded-lg border border-rose-200 bg-rose-50/40 space-y-1"
                            >
                              <div className="flex items-center justify-between gap-2">
                                <div className="flex items-center gap-2">
                                  <span className="text-xs font-bold line-through text-slate-400">
                                    {w.employee_name}
                                  </span>
                                  {w.tally_id && (
                                    <span className="font-mono text-[10px] text-slate-400">({w.tally_id})</span>
                                  )}
                                  <span className="text-[9px] font-bold text-rose-700 bg-rose-100 px-1.5 py-0.2 rounded">
                                    Pending Base Removal
                                  </span>
                                </div>

                                <button
                                  type="button"
                                  onClick={() => handleUndoStageBaseRemoval(w.employee_id)}
                                  className="px-2 py-1 rounded text-slate-700 hover:bg-slate-200 text-xs font-semibold flex items-center gap-1 border border-slate-300 bg-white"
                                >
                                  <Undo2 className="h-3.5 w-3.5" /> Undo
                                </button>
                              </div>
                              <div className="text-[11px] text-rose-700 flex items-center gap-1">
                                <FileText className="h-3 w-3 text-rose-400 shrink-0" />
                                <span>Reason: {stagedBaseInfo?.reason}</span>
                              </div>
                            </div>
                          );
                        }

                        const isPromptingRemoval = removingBaseWorkerId === w.employee_id;

                        return (
                          <div
                            key={idx}
                            className="p-3 rounded-lg border border-slate-200 bg-slate-50 space-y-2"
                          >
                            <div className="flex items-center justify-between gap-2">
                              <div className="flex items-center gap-2">
                                <span className="text-xs font-bold text-slate-900">{w.employee_name}</span>
                                {w.tally_id && (
                                  <span className="font-mono text-[10px] text-slate-400">({w.tally_id})</span>
                                )}
                                {w.display_type === "TO_BE_COVERED" ? (
                                  <span className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold bg-amber-100 text-amber-800 border border-amber-300 flex items-center gap-1">
                                    <AlertTriangle className="h-2.5 w-2.5 text-amber-600" />
                                    To Be Covered
                                  </span>
                                ) : (
                                  <span className="text-[9px] px-1.5 py-0.5 rounded uppercase font-bold bg-slate-200 text-slate-700">
                                    Blueprint
                                  </span>
                                )}
                              </div>

                              {!isPromptingRemoval && (
                                <div className="flex items-center gap-2">
                                  <button
                                    type="button"
                                    onClick={() => setReplacementTargetId(w.employee_id)}
                                    className={`px-2.5 py-1 rounded text-xs font-semibold transition-colors ${
                                      replacementTargetId === w.employee_id
                                        ? "bg-amber-600 text-white shadow-sm"
                                        : w.display_type === "TO_BE_COVERED"
                                        ? "bg-amber-100 text-amber-900 hover:bg-amber-200 border border-amber-300 font-bold"
                                        : "bg-indigo-50 text-indigo-700 hover:bg-indigo-100 border border-indigo-200"
                                    }`}
                                  >
                                    {replacementTargetId === w.employee_id
                                      ? "Target Selected"
                                      : w.display_type === "TO_BE_COVERED"
                                      ? "Select Cover"
                                      : "Replace with Cover"}
                                  </button>
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setRemovingBaseWorkerId(w.employee_id);
                                      setBaseRemovalReasonInput("");
                                    }}
                                    className="px-2.5 py-1 rounded text-xs font-semibold text-rose-700 bg-rose-50 hover:bg-rose-100 border border-rose-200 flex items-center gap-1"
                                  >
                                    <Trash2 className="h-3.5 w-3.5" /> Remove Base Shift
                                  </button>
                                </div>
                              )}
                            </div>

                            {isPromptingRemoval ? (
                              <div className="p-2.5 rounded-lg bg-rose-50 border border-rose-200 space-y-2 mt-2">
                                <label className="block text-[11px] font-semibold text-rose-900">
                                  Removal Reason (Mandatory):
                                </label>
                                <input
                                  type="text"
                                  value={baseRemovalReasonInput}
                                  onChange={(e) => setBaseRemovalReasonInput(e.target.value)}
                                  placeholder="e.g. Site closed, client requested cancellation..."
                                  autoFocus
                                  className="w-full text-xs py-1.5 px-2.5 rounded border border-rose-300 bg-white focus:outline-none focus:ring-1 focus:ring-rose-500"
                                />
                                <div className="flex items-center justify-end gap-2 pt-1">
                                  <button
                                    type="button"
                                    onClick={() => {
                                      setRemovingBaseWorkerId(null);
                                      setBaseRemovalReasonInput("");
                                    }}
                                    className="px-2.5 py-1 rounded text-xs font-semibold text-slate-600 hover:bg-slate-200"
                                  >
                                    Cancel
                                  </button>
                                  <button
                                    type="button"
                                    disabled={!baseRemovalReasonInput.trim()}
                                    onClick={() => handleConfirmStageBaseRemoval(w)}
                                    className="px-3 py-1 rounded text-xs font-semibold bg-rose-600 text-white hover:bg-rose-700 disabled:opacity-50"
                                  >
                                    Confirm Removal
                                  </button>
                                </div>
                              </div>
                            ) : (
                              <div className="text-[11px] text-slate-500 flex items-center gap-2">
                                <span>{w.assigned_hours} hrs</span>
                                <span>•</span>
                                <span>Base recurring template</span>
                              </div>
                            )}
                          </div>
                        );
                      }

                      // Case C: Operational Shifts (Direct or Cover with shift_id)
                      return (
                        <div
                          key={idx}
                          className={`p-3 rounded-lg border transition-all ${
                            isShiftMarkedForRemoval
                              ? "bg-red-50/50 border-red-200 opacity-70"
                              : "bg-slate-50 border-slate-200"
                          }`}
                        >
                          <div className="flex items-center justify-between gap-2">
                            <div className="flex items-center gap-2">
                              <span
                                className={`text-xs font-bold ${
                                  isShiftMarkedForRemoval ? "line-through text-slate-400" : "text-slate-900"
                                }`}
                              >
                                {w.employee_name}
                              </span>
                              {w.tally_id && (
                                <span className="font-mono text-[10px] text-slate-400">({w.tally_id})</span>
                              )}
                              <span
                                className={`text-[9px] px-1.5 py-0.5 rounded uppercase font-bold ${
                                  w.display_type === "OVERRIDE"
                                    ? "bg-indigo-100 text-indigo-800"
                                    : "bg-emerald-100 text-emerald-800"
                                }`}
                              >
                                {w.display_type === "OVERRIDE" ? "Cover" : "Additional"}
                              </span>
                              {isShiftMarkedForRemoval && (
                                <span className="text-[9px] font-bold text-red-700 bg-red-100 px-1.5 py-0.2 rounded">
                                  Pending Removal
                                </span>
                              )}
                            </div>

                            {isShiftMarkedForRemoval ? (
                              <button
                                type="button"
                                onClick={() => handleUndoRemoveShift(w.shift_id!)}
                                className="px-2 py-1 rounded text-slate-700 hover:bg-slate-200 text-xs font-semibold flex items-center gap-1 border border-slate-300"
                              >
                                <Undo2 className="h-3.5 w-3.5" /> Undo
                              </button>
                            ) : (
                              <button
                                type="button"
                                onClick={() => handleStageRemoveShift(w.shift_id!)}
                                className="px-2 py-1 rounded text-red-700 hover:bg-red-50 text-xs font-semibold flex items-center gap-1 border border-red-200 bg-white"
                              >
                                <Trash2 className="h-3.5 w-3.5" /> Remove Shift
                              </button>
                            )}
                          </div>

                          <div className="text-[11px] text-slate-500 mt-1 flex flex-wrap items-center gap-3">
                            <span>{w.assigned_hours} hrs</span>
                            <span>•</span>
                            <span className="flex items-center gap-1 italic text-slate-600">
                              <FileText className="h-3 w-3 text-slate-400 shrink-0" />
                              Reason: {w.reason || "Standard shift"}
                            </span>
                            {w.original_employee_name && (
                              <>
                                <span>•</span>
                                <span className="text-indigo-600 font-medium">
                                  Covering: {w.original_employee_name}
                                </span>
                              </>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>

              {/* 2. Staged Additions (Newly Added Operational Workers) */}
              {stagedAdditions.length > 0 && (
                <div className="space-y-2 pt-2 border-t border-slate-200">
                  <div className="flex items-center justify-between">
                    <h4 className="text-xs font-bold uppercase tracking-wider text-emerald-800 flex items-center gap-1.5">
                      <Sparkles className="h-4 w-4 text-emerald-600" />
                      Staged Additions ({stagedAdditions.length})
                    </h4>
                    <span className="text-[10px] font-bold text-emerald-700 bg-emerald-50 border border-emerald-200 px-2 py-0.5 rounded">
                      Not saved yet
                    </span>
                  </div>

                  <div className="space-y-2">
                    {stagedAdditions.map((addition) => (
                      <div
                        key={addition.tempId}
                        className="p-3 rounded-lg border border-emerald-200 bg-emerald-50/40 space-y-2"
                      >
                        <div className="flex items-center justify-between gap-2">
                          <div className="flex items-center gap-2">
                            <span className="text-xs font-bold text-slate-900">{addition.employee_name}</span>
                            {addition.tally_id && (
                              <span className="font-mono text-[10px] text-slate-400">({addition.tally_id})</span>
                            )}
                            <span
                              className={`text-[9px] px-1.5 py-0.5 rounded uppercase font-bold ${
                                addition.source === "OVERRIDE"
                                  ? "bg-indigo-100 text-indigo-800"
                                  : "bg-emerald-100 text-emerald-800"
                              }`}
                            >
                              {addition.source === "OVERRIDE" ? "Cover" : "Additional"}
                            </span>
                            {addition.original_employee_name && (
                              <span className="text-[10px] text-indigo-700">
                                (Replacing: {addition.original_employee_name})
                              </span>
                            )}
                            {addition.is_rest_day && (
                              <span className="text-[9px] font-bold text-amber-800 bg-amber-100 px-1.5 py-0.2 rounded border border-amber-200">
                                Rest Day Overtime
                              </span>
                            )}
                          </div>

                          <button
                            type="button"
                            onClick={() => handleRemoveStagedAddition(addition.tempId)}
                            className="text-slate-400 hover:text-red-600 p-1 rounded hover:bg-slate-100"
                            title="Remove addition"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>

                        {/* Editable inputs for Hours and Reason/Note */}
                        <div className="grid grid-cols-1 sm:grid-cols-3 gap-2 pt-1">
                          <div className="sm:col-span-1">
                            <label className="block text-[10px] font-semibold text-slate-600 mb-0.5">
                              Assigned Hours
                            </label>
                            <input
                              type="number"
                              step="0.5"
                              value={addition.assigned_hours}
                              onChange={(e) =>
                                handleUpdateStagedHours(addition.tempId, parseFloat(e.target.value) || 0)
                              }
                              className="w-full text-xs py-1 px-2 rounded border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                            />
                          </div>
                          <div className="sm:col-span-2">
                            <label className="block text-[10px] font-semibold text-slate-600 mb-0.5">
                              Reason / Shift Note
                            </label>
                            <input
                              type="text"
                              value={addition.override_reason}
                              onChange={(e) => handleUpdateStagedReason(addition.tempId, e.target.value)}
                              placeholder="Reason / note..."
                              className="w-full text-xs py-1 px-2 rounded border border-slate-300 bg-white focus:outline-none focus:ring-1 focus:ring-indigo-500"
                            />
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Public Holiday Warning Banner */}
              {selectedCell.cell.is_public_holiday && (
                <div className="p-3 rounded-lg bg-sky-50 border border-sky-200 text-xs text-sky-900 flex items-center gap-2">
                  <AlertTriangle className="h-4 w-4 text-sky-600 shrink-0" />
                  <span>
                    <strong>Public Holiday:</strong> {selectedCell.cell.holiday_name || "Public Holiday"}. Statutory holiday overtime rates apply.
                  </span>
                </div>
              )}

              {/* 3. Assign Candidates & Crew */}
              <div className="pt-3 border-t border-slate-200 space-y-3">
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                  <h4 className="text-xs font-bold uppercase tracking-wider text-slate-700 flex items-center gap-1.5">
                    <UserCheck className="h-4 w-4 text-indigo-600" />
                    {replacementTargetId ? "Select Replacement Worker" : "Add Operational Worker"}
                  </h4>

                  {selectedSupervisorId && (
                    <label className="text-xs font-medium text-indigo-700 flex items-center gap-1.5 cursor-pointer bg-indigo-50 px-2 py-0.5 rounded border border-indigo-200">
                      <input
                        type="checkbox"
                        checked={filterToSupervisorCrew}
                        onChange={(e) => setFilterToSupervisorCrew(e.target.checked)}
                        className="rounded border-indigo-300 text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                      />
                      <span>Filter to Selected Supervisor's Crew</span>
                    </label>
                  )}
                </div>

                {replacementTargetId && (
                  <div className="p-2.5 rounded-lg bg-indigo-50 border border-indigo-200 text-indigo-800 text-xs flex items-center justify-between">
                    <span>
                      Replacing base worker:{" "}
                      <strong>
                        {selectedCell.cell.workers.find((w) => w.employee_id === replacementTargetId)?.employee_name}
                      </strong>
                    </span>
                    <button
                      onClick={() => setReplacementTargetId(null)}
                      className="text-indigo-950 font-bold hover:underline"
                    >
                      Clear
                    </button>
                  </div>
                )}

                {/* Candidate Search */}
                <div className="relative">
                  <Search className="absolute left-3 top-2.5 h-3.5 w-3.5 text-slate-400" />
                  <input
                    type="text"
                    placeholder="Search candidate by name, ID or grade..."
                    value={candidateSearch}
                    onChange={(e) => setCandidateSearch(e.target.value)}
                    className="w-full pl-8 pr-3 py-1.5 text-xs rounded-lg border border-slate-200 bg-white focus:outline-none focus:ring-2 focus:ring-indigo-500"
                  />
                </div>

                {/* Candidate List */}
                {loadingCandidates ? (
                  <div className="text-xs text-slate-400 py-4 text-center">Loading candidates...</div>
                ) : filteredCandidates.length === 0 ? (
                  <div className="text-xs text-slate-400 py-4 text-center italic">
                    No matching available candidates found for this slot.
                  </div>
                ) : (
                  <div className="space-y-1.5 max-h-52 overflow-y-auto pr-1">
                    {filteredCandidates.map((cand) => {
                      const isOffDay = isSameWeekday(cand.weekly_off_day, selectedCell.cell.weekday);
                      const isBlocked = cand.is_blocked;
                      const remainingHours = Math.max(0, Number(cand.standard_hours) - Number(cand.today_allocated_hours || 0));

                      return (
                        <div
                          key={cand.employee_id}
                          className={`p-2.5 rounded-lg border flex items-center justify-between text-xs transition-colors ${
                            isBlocked
                              ? "bg-slate-50 border-slate-200 opacity-60 text-slate-400"
                              : "bg-white border-slate-200 hover:border-indigo-300 text-slate-800"
                          }`}
                        >
                          <div className="space-y-0.5">
                            <div className="flex items-center gap-2">
                              <span className="font-semibold">{cand.name}</span>
                              <span className="font-mono text-[10px] text-slate-400">({cand.tally_id})</span>
                              {cand.exact_staff_type_match && (
                                <span className="text-[9px] font-bold text-amber-700 bg-amber-50 px-1 rounded">
                                  * Exact Match
                                </span>
                              )}
                            </div>
                            <div className="text-[10px] text-slate-500 flex items-center gap-2">
                              <span>{cand.staff_grade_description}</span>
                              <span>•</span>
                              <span className={isOffDay ? "text-amber-700 font-bold" : ""}>
                                Off: {cand.weekly_off_day || "None"}
                              </span>
                            </div>

                            {/* Capacity or Blocked reason */}
                            {cand.is_blocked ? (
                              <div className="text-[10px] text-rose-700 font-semibold flex items-center gap-1 mt-0.5">
                                <span className="px-1.5 py-0.2 rounded bg-rose-50 border border-rose-200">
                                  Blocked: {cand.blocked_reason}
                                </span>
                              </div>
                            ) : (
                              <div className="flex items-center gap-1.5 mt-0.5">
                                {Number(cand.today_allocated_hours || 0) > 0 ? (
                                  <span className="text-[9px] font-semibold text-indigo-700 bg-indigo-50 border border-indigo-200 px-1.5 py-0.5 rounded">
                                    Remote: {cand.today_allocated_hours}h / {cand.standard_hours}h ({remainingHours.toFixed(1)}h left)
                                  </span>
                                ) : (
                                  <span className="text-[9px] text-slate-500 bg-slate-50 border border-slate-200 px-1.5 py-0.5 rounded">
                                    Available ({cand.standard_hours}h standard)
                                  </span>
                                )}
                              </div>
                            )}
                          </div>

                          <button
                            type="button"
                            disabled={isBlocked}
                            onClick={() => handleAddCandidateToStaged(cand)}
                            className={`px-3 py-1.5 rounded text-xs font-semibold flex items-center gap-1 transition-colors ${
                              isBlocked
                                ? "bg-slate-100 text-slate-400 cursor-not-allowed"
                                : "bg-indigo-50 text-indigo-700 hover:bg-indigo-600 hover:text-white border border-indigo-200"
                            }`}
                          >
                            <Plus className="h-3.5 w-3.5" />
                            {replacementTargetId ? "Add Cover" : "Add Worker"}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>

            {/* Modal Footer */}
            <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
              <div className="text-xs text-slate-500">
                {stagedAdditions.length > 0 || stagedRemovals.size > 0 || stagedBaseRemovals.size > 0 ? (
                  <span className="font-semibold text-indigo-700">
                    Staged: +{stagedAdditions.length} addition(s), -{stagedRemovals.size + stagedBaseRemovals.size} removal(s)
                  </span>
                ) : (
                  <span>No changes staged</span>
                )}
              </div>

              <div className="flex items-center gap-3">
                <button
                  type="button"
                  onClick={handleCancelModal}
                  className="px-4 py-2 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-200 transition-colors"
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={handleSaveOperationalRoster}
                  disabled={savingShift || (stagedAdditions.length === 0 && stagedRemovals.size === 0 && stagedBaseRemovals.size === 0)}
                  className="px-4 py-2 rounded-lg text-xs font-semibold bg-indigo-600 text-white hover:bg-indigo-700 disabled:opacity-50 flex items-center gap-1.5 shadow-sm transition-colors"
                >
                  {savingShift && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                  Save Operational Roster
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Request Temporary Reassignment Modal (D2, BR-SC-04) */}
      {reassignmentModalOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/40 backdrop-blur-xs">
          <div className="bg-white rounded-xl shadow-2xl border border-slate-200 w-full max-w-xl max-h-[92vh] flex flex-col overflow-hidden">
            {/* Modal Header */}
            <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
              <div>
                <h3 className="text-base font-bold text-slate-900 flex items-center gap-2">
                  <Users className="h-5 w-5 text-indigo-600" />
                  Request Temporary Reassignment
                </h3>
                <p className="text-xs text-slate-500 mt-0.5">
                  Operational adjustment for specific dates (requires ≥ 3 days notice per company policy).
                </p>
              </div>
              <button
                type="button"
                onClick={() => setReassignmentModalOpen(false)}
                className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 cursor-pointer"
              >
                <X className="h-5 w-5" />
              </button>
            </div>

            {/* Modal Body / Form */}
            <form onSubmit={handleCreateReassignment} className="flex-1 overflow-y-auto p-6 space-y-4">
              {/* Type Switcher */}
              <div>
                <label className="block text-xs font-bold text-slate-700 uppercase tracking-wider mb-2">
                  Reassignment Type
                </label>
                <div className="grid grid-cols-4 gap-2">
                  {(["REPLACE", "MOVE", "ADD", "CANCEL"] as const).map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => {
                        setReassignType(t);
                        setReassignError(null);
                        setReassignPreview(null);
                      }}
                      className={`py-2 px-2.5 rounded-lg text-xs font-bold text-center border transition cursor-pointer ${
                        reassignType === t
                          ? "bg-indigo-600 text-white border-indigo-600 shadow-xs"
                          : "bg-white text-slate-700 border-slate-200 hover:bg-slate-50"
                      }`}
                    >
                      {t}
                    </button>
                  ))}
                </div>
                <p className="text-2xs text-slate-500 mt-1.5">
                  {reassignType === "REPLACE" && "Assign a replacement worker to cover an absent worker's shift."}
                  {reassignType === "MOVE" && "Relocate a worker from their blueprint site to another job site."}
                  {reassignType === "ADD" && "Deploy an additional worker to a job site for operational need."}
                  {reassignType === "CANCEL" && "Cancel a scheduled shift due to client closure or weather conditions."}
                </p>
              </div>

              {/* Date Selectors & Notice Period Banner */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Date From <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={reassignDateFrom}
                    onChange={(e) => setReassignDateFrom(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  />
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Date To <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="date"
                    required
                    value={reassignDateTo}
                    onChange={(e) => setReassignDateTo(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  />
                </div>
              </div>

              {/* Notice Validation Banner */}
              <div
                className={`p-3 rounded-lg border text-xs flex items-center justify-between gap-2 ${
                  noticeDays >= 3
                    ? "bg-emerald-50 border-emerald-200 text-emerald-800"
                    : "bg-rose-50 border-rose-200 text-rose-800"
                }`}
              >
                <div className="flex items-center gap-2">
                  {noticeDays >= 3 ? (
                    <CheckCircle2 className="h-4 w-4 text-emerald-600 shrink-0" />
                  ) : (
                    <AlertTriangle className="h-4 w-4 text-rose-600 shrink-0" />
                  )}
                  <span>
                    {noticeDays >= 3
                      ? `${noticeDays} days advance notice (Valid notice period per BR-SC-04)`
                      : `Notice is ${noticeDays} day(s). System requires strictly ≥ 3 days notice.`}
                  </span>
                </div>
                <span className="text-2xs font-extrabold uppercase tracking-wide">
                  {noticeDays >= 3 ? "Allowed" : user?.role === "ADMIN" ? "Admin Override" : "Refused"}
                </span>
              </div>

              {/* Original Worker (REPLACE, MOVE, CANCEL) */}
              {(reassignType === "REPLACE" || reassignType === "MOVE" || reassignType === "CANCEL") && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Original Worker (Absent / Being Moved) <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={reassignOrigEmpId}
                    onChange={(e) => setReassignOrigEmpId(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="">-- Select Worker --</option>
                    {availableEmployees.map((emp: any) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name || emp.employee_name} ({emp.tally_id || "No Tally"} • {emp.staff_grade_description || emp.role || "Worker"})
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Target Worksite & Job Item (REPLACE, MOVE, ADD) */}
              {(reassignType === "REPLACE" || reassignType === "MOVE" || reassignType === "ADD") && (
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Target Worksite & Job Item <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={reassignJobItemId}
                    onChange={(e) => setReassignJobItemId(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="">-- Select Target Job Item --</option>
                    {availableJobItems.map((j) => (
                      <option key={j.job_item_id} value={j.job_item_id}>
                        {j.label}
                      </option>
                    ))}
                  </select>
                </div>
              )}

              {/* Replacement / New Worker (REPLACE, ADD) */}
              {(reassignType === "REPLACE" || reassignType === "ADD") && (
                <div>
                  <div className="flex items-center justify-between mb-1">
                    <label className="block text-xs font-semibold text-slate-700">
                      Replacement / New Worker <span className="text-rose-500">*</span>
                    </label>
                    <button
                      type="button"
                      onClick={handlePreviewReassignment}
                      disabled={previewLoading || !reassignNewEmpId}
                      className="text-xs text-indigo-600 hover:text-indigo-800 font-bold flex items-center gap-1 disabled:opacity-40 cursor-pointer"
                    >
                      {previewLoading ? <Loader2 className="h-3 w-3 animate-spin" /> : <Sparkles className="h-3 w-3" />}
                      Preview Worker Hours
                    </button>
                  </div>
                  <select
                    value={reassignNewEmpId}
                    onChange={(e) => setReassignNewEmpId(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="">-- Select Replacement Worker --</option>
                    {availableEmployees.map((emp: any) => (
                      <option key={emp.id} value={emp.id}>
                        {emp.name || emp.employee_name} ({emp.tally_id || "No Tally"} • {emp.staff_grade_description || emp.role || "Worker"})
                      </option>
                    ))}
                  </select>

                  {/* Preview Result Card */}
                  {reassignPreview && (
                    <div className="mt-2.5 p-3 rounded-lg bg-indigo-50/70 border border-indigo-200 text-xs space-y-1">
                      <div className="font-bold text-indigo-900 flex items-center justify-between">
                        <span>Projected Total Weekly Hours: {reassignPreview.total_weekly_hours}h</span>
                        {reassignPreview.planned_overtime_hours > 0 && (
                          <span className="text-amber-700 font-bold">
                            OT: +{reassignPreview.planned_overtime_hours}h
                          </span>
                        )}
                      </div>
                      {reassignPreview.warnings?.length > 0 ? (
                        <div className="text-rose-700 space-y-0.5 pt-1">
                          {reassignPreview.warnings.map((w: string, idx: number) => (
                            <div key={idx} className="flex items-center gap-1">
                              <AlertCircle className="h-3 w-3 shrink-0" />
                              <span>{w}</span>
                            </div>
                          ))}
                        </div>
                      ) : (
                        <p className="text-2xs text-emerald-700 font-medium">
                          ✓ No schedule conflicts or overtime violations detected.
                        </p>
                      )}
                    </div>
                  )}
                </div>
              )}

              {/* Reason Category & Reason */}
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Reason Category <span className="text-rose-500">*</span>
                  </label>
                  <select
                    value={reassignReasonCategory}
                    onChange={(e) => setReassignReasonCategory(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  >
                    <option value="LEAVE_COVER">Leave Cover Absence</option>
                    <option value="CAPACITY">Operational Capacity Shortfall</option>
                    <option value="WEATHER">Weather Conditions</option>
                    <option value="PRIORITY">High-Priority Client Request</option>
                    <option value="OTHER">Other Operational Need</option>
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-semibold text-slate-700 mb-1">
                    Reason Details <span className="text-rose-500">*</span>
                  </label>
                  <input
                    type="text"
                    required
                    placeholder="e.g. Covering sick leave for gardener..."
                    value={reassignReason}
                    onChange={(e) => setReassignReason(e.target.value)}
                    className="w-full text-xs font-medium text-slate-900 border border-slate-200 rounded-lg p-2 bg-slate-50 focus:bg-white focus:outline-indigo-500"
                  />
                </div>
              </div>

              {/* Errors & Success Banners */}
              {reassignError && (
                <div className="p-3 bg-rose-50 border border-rose-200 text-rose-800 text-xs rounded-lg flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 shrink-0" />
                  <span>{reassignError}</span>
                </div>
              )}
              {reassignSuccess && (
                <div className="p-3 bg-emerald-50 border border-emerald-200 text-emerald-800 text-xs rounded-lg flex items-center gap-2">
                  <CheckCircle2 className="h-4 w-4 shrink-0" />
                  <span>{reassignSuccess}</span>
                </div>
              )}

              {/* Modal Footer Actions */}
              <div className="pt-3 border-t border-slate-100 flex items-center justify-between">
                <span className="text-2xs text-slate-400">
                  Engineer or Admin approval required before operational schedule is updated.
                </span>
                <div className="flex items-center gap-2">
                  <button
                    type="button"
                    onClick={() => setReassignmentModalOpen(false)}
                    className="px-3.5 py-1.5 rounded-lg text-xs font-semibold text-slate-600 hover:bg-slate-100 transition cursor-pointer"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={reassignSubmitting || (noticeDays < 3 && user?.role !== "ADMIN")}
                    className="px-4 py-1.5 rounded-lg text-xs font-semibold bg-indigo-600 hover:bg-indigo-700 disabled:opacity-50 text-white flex items-center gap-1.5 shadow-xs transition cursor-pointer"
                  >
                    {reassignSubmitting && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                    Submit Reassignment Request
                  </button>
                </div>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
};
