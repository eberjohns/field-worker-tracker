import React, { useState, useEffect } from "react";
import {
  X,
  AlertTriangle,
  Users,
  CheckCircle2,
  Trash2,
  Zap,
  Calendar,
  Layers,
  Star,
  Loader2,
} from "lucide-react";
import { CoverageItemRow, CoverageDayCell, CandidateRecommendation } from "./types";

interface AssignModalProps {
  isOpen: boolean;
  onClose: () => void;
  onSuccess: () => void;
  token: string | null;
  targetJobItem?: CoverageItemRow | null;
  targetDay?: CoverageDayCell | null;
  worksiteInfo?: { id: string; job_number: string; job_name: string } | null;
  // Fallbacks if opened from worker view
  initialWorkerId?: string | null;
  initialJobItemId?: string | null;
  initialDate?: string | null;
  availableJobItems?: any[];
}

export const AssignModal: React.FC<AssignModalProps> = ({
  isOpen,
  onClose,
  onSuccess,
  token,
  targetJobItem,
  targetDay,
  worksiteInfo,
  initialWorkerId,
  initialJobItemId,
  initialDate,
  availableJobItems = [],
}) => {
  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [selectedWorkerIds, setSelectedWorkerIds] = useState<string[]>([]);
  const [assignedDetails, setAssignedDetails] = useState<any[]>([]);
  const [isStandingTeam, setIsStandingTeam] = useState<boolean>(false);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  // Active Job Item and Date resolution
  const activeJobItem =
    targetJobItem ||
    (initialJobItemId ? availableJobItems.find((j) => j.id === initialJobItemId) : null);

  const activeDate =
    targetDay?.work_date || initialDate || new Date().toISOString().split("T")[0];

  const requiredCount = activeJobItem?.required_staff_count || 1;
  const currentAssignedCount = assignedDetails.length;
  const neededCount = Math.max(0, requiredCount - currentAssignedCount);

  const authHeaders = {
    "Content-Type": "application/json",
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
  };

  // Fetch candidates and sync current assignments when opened
  useEffect(() => {
    if (!isOpen) return;

    setErrorMsg(null);
    setSelectedWorkerIds(initialWorkerId ? [initialWorkerId] : []);
    setAssignedDetails(targetDay?.assigned_details || []);

    const fetchRecommendations = async () => {
      const jId = activeJobItem?.job_item_id || activeJobItem?.id || initialJobItemId;
      if (!jId) return;

      setLoadingCandidates(true);
      try {
        const res = await fetch(
          `/api/v1/job-items/${jId}/recommendations?date=${activeDate}`,
          { headers: authHeaders }
        );
        if (res.ok) {
          const data: CandidateRecommendation[] = await res.json();
          setCandidates(data);
        } else {
          const err = await res.json();
          setErrorMsg(err.detail || "Failed to load candidate recommendations.");
        }
      } catch (err: any) {
        setErrorMsg(err.message || "Failed to load candidate recommendations.");
      } finally {
        setLoadingCandidates(false);
      }
    };

    fetchRecommendations();
  }, [isOpen, activeJobItem?.job_item_id, activeJobItem?.id, initialJobItemId, activeDate]);

  if (!isOpen) return null;

  // Toggle selection
  const toggleSelectWorker = (empId: string) => {
    if (selectedWorkerIds.includes(empId)) {
      setSelectedWorkerIds(selectedWorkerIds.filter((id) => id !== empId));
    } else {
      setSelectedWorkerIds([...selectedWorkerIds, empId]);
    }
  };

  // Shortcut: Auto-select top N needed workers
  const autoSelectNeeded = () => {
    if (neededCount <= 0 || candidates.length === 0) return;
    const topIds = candidates
      .slice(0, neededCount)
      .map((c) => c.employee_id);
    setSelectedWorkerIds(topIds);
  };

  // Unassign an existing worker
  const handleUnassign = async (scheduledWorkId: string) => {
    try {
      const res = await fetch(`/api/v1/scheduled-work/${scheduledWorkId}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to unassign worker.");
      }
      setAssignedDetails(assignedDetails.filter((a) => a.scheduled_work_id !== scheduledWorkId));
      onSuccess();
    } catch (err: any) {
      alert(err.message);
    }
  };

  // Submit batch assignment
  const handleAssignSubmit = async () => {
    if (selectedWorkerIds.length === 0) return;
    const jId = activeJobItem?.job_item_id || activeJobItem?.id || initialJobItemId;
    if (!jId) return;

    setSubmitting(true);
    setErrorMsg(null);

    try {
      const res = await fetch("/api/v1/scheduled-work/batch", {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          employee_ids: selectedWorkerIds,
          job_item_id: jId,
          work_date: activeDate,
          assigned_hours: activeJobItem?.hours_per_occurrence,
          as_standing_assignment: isStandingTeam,
          acknowledge_warnings: true,
        }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to assign workers.");
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred while assigning workers.");
    } finally {
      setSubmitting(false);
    }
  };

  // Find supervisor of selected candidates to boost same group
  const selectedSupervisors = new Set(
    candidates
      .filter((c) => selectedWorkerIds.includes(c.employee_id) && c.supervisor_id)
      .map((c) => c.supervisor_id)
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-slate-900/60 backdrop-blur-xs p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 w-full max-w-3xl max-h-[92vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Modal Header */}
        <div className="px-6 py-4 border-b border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-10 w-10 rounded-xl bg-blue-600 text-white flex items-center justify-center font-bold text-base shadow-sm">
              <Users className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <h2 className="text-base font-bold text-slate-900">
                  Assign Staff to Job Requirement
                </h2>
                <span className="px-2 py-0.5 rounded text-[11px] font-bold bg-blue-100 text-blue-800 border border-blue-200">
                  Required: {activeJobItem?.planned_grade_code || "Any"}
                </span>
              </div>
              <p className="text-xs text-slate-500 flex items-center space-x-2 mt-0.5">
                <span className="font-semibold text-slate-700">
                  {worksiteInfo?.job_number || activeJobItem?.job_number || "Site"}
                </span>
                <span>•</span>
                <span>{worksiteInfo?.job_name || activeJobItem?.job_name || "Job"}</span>
                <span>•</span>
                <span className="font-medium text-blue-700">
                  Item {activeJobItem?.sub_item_code}: {activeJobItem?.staff_grade_description}
                </span>
              </p>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Staffing Status Banner */}
        <div className="px-6 py-3 bg-blue-50/70 border-b border-blue-100 flex flex-wrap items-center justify-between gap-3 text-xs">
          <div className="flex items-center space-x-4">
            <div className="flex items-center space-x-1.5 text-slate-700">
              <Calendar className="h-4 w-4 text-blue-600" />
              <span>
                Date: <strong className="font-mono text-slate-900">{activeDate}</strong>
              </span>
            </div>
            <div className="flex items-center space-x-1.5 text-slate-700">
              <Layers className="h-4 w-4 text-blue-600" />
              <span>
                Daily: <strong>{Number(activeJobItem?.hours_per_occurrence || 8).toFixed(1)}h</strong>
              </span>
            </div>
          </div>

          <div className="flex items-center space-x-3">
            <span className="text-slate-600">
              Required: <strong>{requiredCount}</strong>
            </span>
            <span className="text-slate-400">|</span>
            <span className="text-slate-600">
              Assigned: <strong>{currentAssignedCount}</strong>
            </span>
            <span className="text-slate-400">|</span>
            <span
              className={`px-2 py-0.5 rounded-full font-bold ${
                neededCount > 0 ? "bg-amber-100 text-amber-800" : "bg-emerald-100 text-emerald-800"
              }`}
            >
              {neededCount > 0 ? `${neededCount} worker(s) needed` : "Fully Staffed"}
            </span>
          </div>
        </div>

        {/* Content Body */}
        <div className="flex-1 overflow-y-auto p-6 space-y-6">
          {errorMsg && (
            <div className="p-3 bg-red-50 border border-red-200 text-red-700 rounded-xl text-xs flex items-center space-x-2">
              <AlertTriangle className="h-4 w-4 shrink-0 text-red-600" />
              <span>{errorMsg}</span>
            </div>
          )}

          {/* 1. Currently Assigned Workers Section */}
          {assignedDetails.length > 0 && (
            <div className="space-y-2">
              <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                Currently Assigned on this Slot ({assignedDetails.length})
              </h4>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {assignedDetails.map((a: any) => (
                  <div
                    key={a.scheduled_work_id}
                    className="p-2.5 rounded-xl border border-emerald-200 bg-emerald-50/40 flex items-center justify-between text-xs shadow-2xs"
                  >
                    <div>
                      <div className="font-bold text-slate-800">{a.name}</div>
                      <div className="text-[11px] text-slate-500 font-mono">{a.tally_id}</div>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleUnassign(a.scheduled_work_id)}
                      className="px-2 py-1 rounded-lg text-[10px] font-semibold text-red-700 bg-white border border-red-200 hover:bg-red-50 flex items-center space-x-1 transition"
                      title="Unassign worker from this slot"
                    >
                      <Trash2 className="h-3 w-3" />
                      <span>Unassign</span>
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2. Eligible Candidates Section */}
          <div className="space-y-3">
            <div className="flex items-center justify-between">
              <div>
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Recommended Candidates (Grade: {activeJobItem?.planned_grade_code})
                </h4>
                <p className="text-[11px] text-slate-500">
                  Workers from the same supervisor crew on this site are ranked first
                </p>
              </div>

              {neededCount > 0 && candidates.length > 0 && (
                <button
                  type="button"
                  onClick={autoSelectNeeded}
                  className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100 flex items-center space-x-1.5 transition shadow-2xs"
                >
                  <Zap className="h-3.5 w-3.5 fill-amber-500 text-amber-600" />
                  <span>Auto-Check Top {neededCount} Needed</span>
                </button>
              )}
            </div>

            {loadingCandidates ? (
              <div className="p-12 text-center text-xs text-blue-700 flex flex-col items-center justify-center space-y-2">
                <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                <span>Loading eligible candidates and crew recommendations...</span>
              </div>
            ) : candidates.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 bg-slate-50 rounded-xl border border-slate-200">
                No eligible workers found matching grade group {activeJobItem?.planned_grade_code}.
              </div>
            ) : (
              <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl max-h-72 overflow-y-auto">
                {candidates.map((worker) => {
                  const isChecked = selectedWorkerIds.includes(worker.employee_id);
                  const sharesCrewWithSelected =
                    worker.supervisor_id && selectedSupervisors.has(worker.supervisor_id);

                  return (
                    <div
                      key={worker.employee_id}
                      onClick={() => toggleSelectWorker(worker.employee_id)}
                      className={`p-3 flex items-start space-x-3 cursor-pointer transition text-xs ${
                        isChecked
                          ? "bg-blue-50/80 border-l-4 border-l-blue-600"
                          : worker.shares_site_group
                          ? "bg-amber-50/30 hover:bg-amber-50/60"
                          : "hover:bg-slate-50"
                      }`}
                    >
                      {/* Checkbox */}
                      <input
                        type="checkbox"
                        checked={isChecked}
                        onChange={() => {}} // handled by parent div
                        className="mt-0.5 rounded text-blue-600 focus:ring-blue-500 h-4 w-4 shrink-0"
                      />

                      {/* Candidate Info */}
                      <div className="flex-1 space-y-1">
                        <div className="flex items-center justify-between">
                          <div className="font-bold text-slate-900 flex items-center space-x-1.5">
                            <span>{worker.name}</span>
                            <span className="font-mono text-[11px] text-slate-500 font-normal">
                              ({worker.tally_id})
                            </span>
                            {worker.exact_staff_type_match && (
                              <span
                                title="Exact staff type match"
                                className="inline-flex items-center text-amber-500 font-bold"
                              >
                                <Star className="h-3 w-3 fill-amber-400 text-amber-500" />
                              </span>
                            )}
                          </div>

                          <div className="flex items-center space-x-2">
                            <span className="font-semibold text-slate-700 bg-slate-100 px-1.5 py-0.5 rounded text-[10px]">
                              {worker.grade_code || "No Grade"}
                            </span>
                            <span className="text-[10px] text-slate-500">
                              Std: {worker.standard_hours}h
                            </span>
                          </div>
                        </div>

                        {/* SGD and Supervisor Crew */}
                        <div className="flex flex-wrap items-center gap-1.5 text-[11px]">
                          <span className="text-slate-600 font-medium">
                            {worker.staff_grade_description}
                          </span>

                          {/* Supervisor / Group Tag */}
                          {worker.supervisor_name && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-medium bg-slate-100 text-slate-700">
                              Crew: {worker.supervisor_name}
                            </span>
                          )}

                          {/* Same Site Group Tag */}
                          {worker.shares_site_group && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-amber-100 text-amber-800 flex items-center space-x-1">
                              <span>★ Same Crew on Site</span>
                            </span>
                          )}

                          {/* Linked to selected worker's group */}
                          {sharesCrewWithSelected && !worker.shares_site_group && (
                            <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-blue-100 text-blue-800">
                              Same Crew as Selected
                            </span>
                          )}
                        </div>

                        {/* Reasons / Warnings */}
                        {worker.reasons.length > 0 && (
                          <div className="text-[10px] text-blue-700 flex flex-wrap gap-1 pt-0.5">
                            {worker.reasons.slice(0, 2).map((r, rIdx) => (
                              <span key={rIdx} className="bg-blue-50 px-1 py-0.2 rounded">
                                ✓ {r}
                              </span>
                            ))}
                          </div>
                        )}
                        {worker.warnings.length > 0 && (
                          <div className="text-[10px] text-amber-700 flex items-center space-x-1">
                            <AlertTriangle className="h-3 w-3 shrink-0" />
                            <span>{worker.warnings[0]}</span>
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* 3. Standing Team Option */}
          <div className="p-3.5 bg-slate-50 border border-slate-200 rounded-xl space-y-1">
            <label className="flex items-center space-x-2 cursor-pointer font-medium text-xs text-slate-800">
              <input
                type="checkbox"
                checked={isStandingTeam}
                onChange={(e) => setIsStandingTeam(e.target.checked)}
                className="rounded text-blue-600 focus:ring-blue-500 h-4 w-4"
              />
              <span className="font-bold">Set as Standing Team (Year Plan)</span>
            </label>
            <p className="text-[11px] text-slate-500 pl-6">
              When checked, automatically materializes daily scheduled visits for the whole contract
              year (13-month rolling horizon) on active working days.
            </p>
          </div>
        </div>

        {/* Modal Footer */}
        <div className="px-6 py-4 border-t border-slate-200 bg-slate-50 flex items-center justify-between">
          <div className="text-xs text-slate-600 font-medium">
            Selected: <strong className="text-blue-700 font-bold">{selectedWorkerIds.length}</strong>{" "}
            worker(s)
            {neededCount > 0 && (
              <span className="text-slate-400"> (needed: {neededCount})</span>
            )}
          </div>

          <div className="flex items-center space-x-2">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 rounded-xl text-xs font-semibold text-slate-600 hover:text-slate-900 hover:bg-slate-200 transition"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleAssignSubmit}
              disabled={submitting || selectedWorkerIds.length === 0}
              className="px-5 py-2 rounded-xl text-xs font-bold bg-blue-600 hover:bg-blue-700 text-white disabled:opacity-50 flex items-center space-x-1.5 transition shadow-sm"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-4 w-4 animate-spin mr-1" />
                  <span>Assigning...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-4 w-4 mr-1" />
                  <span>
                    Assign {selectedWorkerIds.length > 0 ? `(${selectedWorkerIds.length})` : ""}{" "}
                    Workers
                  </span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
