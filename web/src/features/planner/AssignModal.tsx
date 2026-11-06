import React, { useState, useEffect } from "react";
import {
  X,
  AlertTriangle,
  Users,
  CheckCircle2,
  Trash2,
  Zap,
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
  selectedSupervisorId?: string | null;
  selectedSupervisorName?: string | null;
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
  selectedSupervisorId,
  selectedSupervisorName,
}) => {
  const [candidates, setCandidates] = useState<CandidateRecommendation[]>([]);
  const [selectedWorkerIds, setSelectedWorkerIds] = useState<string[]>([]);
  const [assignedDetails, setAssignedDetails] = useState<any[]>([]);
  const [isStandingTeam, setIsStandingTeam] = useState<boolean>(false);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [submitting, setSubmitting] = useState<boolean>(false);
  const [unassigningId, setUnassigningId] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);
  const [filterOnlySelectedCrew, setFilterOnlySelectedCrew] = useState<boolean>(
    Boolean(selectedSupervisorId)
  );

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

  // Sync crew filter when modal opens
  useEffect(() => {
    if (isOpen) {
      setFilterOnlySelectedCrew(Boolean(selectedSupervisorId));
    }
  }, [isOpen, selectedSupervisorId]);

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

  // Unassign single date
  const handleUnassignSingle = async (scheduledWorkId: string) => {
    setUnassigningId(scheduledWorkId);
    try {
      const res = await fetch(`/api/v1/scheduled-work/${scheduledWorkId}`, {
        method: "DELETE",
        headers: authHeaders,
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to unassign worker.");
      }
      setAssignedDetails((prev) => prev.filter((a) => a.scheduled_work_id !== scheduledWorkId));
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setUnassigningId(null);
    }
  };

  // Remove worker from standing series
  const handleRemoveStandingSeries = async (standingId: string, version: number = 1) => {
    setUnassigningId(standingId);
    try {
      const res = await fetch(`/api/v1/standing-assignments/${standingId}/end`, {
        method: "POST",
        headers: authHeaders,
        body: JSON.stringify({
          end_date: activeDate,
          version: version,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail || "Failed to end standing assignment.");
      }
      setAssignedDetails((prev) => prev.filter((a) => a.standing_assignment_id !== standingId));
      onSuccess();
    } catch (err: any) {
      setErrorMsg(err.message);
    } finally {
      setUnassigningId(null);
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
      setErrorMsg(err.message || "An error occurred while saving assignments.");
    } finally {
      setSubmitting(false);
    }
  };

  // Crew filtering & candidate partitioning
  const filteredCandidates = candidates.filter((c) => {
    if (filterOnlySelectedCrew && selectedSupervisorId) {
      return c.supervisor_id === selectedSupervisorId;
    }
    return true;
  });

  const availableCandidates = filteredCandidates.filter((c) => !c.is_blocked);
  const blockedCandidates = filteredCandidates.filter((c) => c.is_blocked);

  // Group affinities among selected
  const selectedSupervisors = new Set(
    candidates
      .filter((c) => selectedWorkerIds.includes(c.employee_id) && c.supervisor_id)
      .map((c) => c.supervisor_id)
  );

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="bg-white rounded-2xl shadow-2xl border border-slate-200 max-w-2xl w-full max-h-[90vh] flex flex-col overflow-hidden animate-in fade-in zoom-in-95 duration-150">
        {/* Header */}
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between shrink-0 bg-slate-50">
          <div>
            <div className="flex items-center space-x-2">
              <span className="font-mono text-xs font-bold px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                {worksiteInfo?.job_number || "Worksite"}
              </span>
              <span className="font-bold text-slate-900 text-sm">
                {worksiteInfo?.job_name || "Job Item Assignment"}
              </span>
            </div>
            <div className="text-xs text-slate-500 mt-1 flex items-center space-x-2">
              <span className="font-semibold text-slate-700">
                Item {activeJobItem?.sub_item_code}: {activeJobItem?.staff_grade_description}
              </span>
              <span>•</span>
              <span className="font-mono text-indigo-600 bg-indigo-50 px-1.5 py-0.2 rounded font-semibold">
                Required Grade: {activeJobItem?.planned_grade_code || "—"}
              </span>
              <span>•</span>
              <span className="font-semibold text-indigo-700">
                {activeJobItem?.hours_per_occurrence}h Shift
              </span>
              <span>•</span>
              <span className="font-mono text-slate-600">{activeDate}</span>
            </div>
          </div>

          <button
            onClick={onClose}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-600 hover:bg-slate-200 transition"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        {/* Staffing Status Bar */}
        <div className="px-6 py-2.5 bg-slate-100 border-b border-slate-200 flex items-center justify-between text-xs shrink-0">
          <div className="flex items-center space-x-2">
            <span className="font-semibold text-slate-600">Current Slot Staffing:</span>
            <span className="font-bold text-slate-900">
              {currentAssignedCount} / {requiredCount} Workers
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
            <div className="space-y-2.5 bg-slate-50 p-4 rounded-xl border border-slate-200">
              <div className="flex items-center justify-between">
                <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                  <Users className="h-3.5 w-3.5 text-indigo-600" />
                  <span>Currently Assigned on this Slot ({assignedDetails.length})</span>
                </h4>
                <span className="text-[11px] text-slate-500">
                  {neededCount === 0 ? "Slot requirement fulfilled" : `${neededCount} more worker(s) needed`}
                </span>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                {assignedDetails.map((a: any) => (
                  <div
                    key={a.scheduled_work_id}
                    className="p-3 rounded-lg border border-slate-200 bg-white flex items-center justify-between text-xs shadow-2xs gap-2"
                  >
                    <div>
                      <div className="font-bold text-slate-900">{a.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[11px] text-slate-500 font-mono">{a.tally_id}</span>
                        {a.source === "STANDING" ? (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-indigo-100 text-indigo-700">
                            Standing Series
                          </span>
                        ) : (
                          <span className="px-1.5 py-0.2 rounded text-[9px] font-bold bg-slate-100 text-slate-600">
                            Single Date
                          </span>
                        )}
                      </div>
                    </div>
                    <div className="flex flex-col gap-1 items-end shrink-0">
                      <button
                        type="button"
                        disabled={unassigningId === a.scheduled_work_id}
                        onClick={() => handleUnassignSingle(a.scheduled_work_id)}
                        className="px-2 py-1 rounded text-[10px] font-semibold text-red-700 bg-red-50 hover:bg-red-100 border border-red-200 transition flex items-center gap-1 disabled:opacity-50"
                        title="Remove worker from this date only"
                      >
                        <Trash2 className="h-3 w-3" />
                        <span>Remove (Date Only)</span>
                      </button>

                      {a.standing_assignment_id && (
                        <button
                          type="button"
                          disabled={unassigningId === a.standing_assignment_id}
                          onClick={() =>
                            handleRemoveStandingSeries(
                              a.standing_assignment_id,
                              a.standing_assignment_version || 1
                            )
                          }
                          className="px-2 py-0.5 rounded text-[9px] font-medium text-slate-600 hover:text-red-700 hover:bg-slate-100 border border-slate-200 transition"
                          title="End standing assignment and clear all future occurrences"
                        >
                          Remove from Standing Series
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* 2. Candidate Selection Section */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Recommended Candidates ({activeJobItem?.staff_grade_description} •{" "}
                  {activeJobItem?.planned_grade_code})
                </h4>
                <p className="text-[11px] text-slate-500">
                  Ranked by role match, required grade code, and supervisor crew on site
                </p>
              </div>

              <div className="flex items-center gap-2">
                {selectedSupervisorId && (
                  <label className="flex items-center gap-1.5 text-xs text-slate-700 cursor-pointer bg-slate-50 px-2.5 py-1 rounded-lg border border-slate-200 select-none">
                    <input
                      type="checkbox"
                      checked={filterOnlySelectedCrew}
                      onChange={(e) => setFilterOnlySelectedCrew(e.target.checked)}
                      className="rounded text-indigo-600 focus:ring-indigo-500 h-3.5 w-3.5"
                    />
                    <span className="font-semibold text-slate-800">
                      Show only {selectedSupervisorName || "selected crew"}
                    </span>
                  </label>
                )}

                {neededCount > 0 && availableCandidates.length > 0 && (
                  <button
                    type="button"
                    onClick={() => {
                      const topIds = availableCandidates
                        .slice(0, neededCount)
                        .map((c) => c.employee_id);
                      setSelectedWorkerIds(topIds);
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100 flex items-center space-x-1.5 transition shadow-2xs"
                  >
                    <Zap className="h-3.5 w-3.5 fill-amber-500 text-amber-600" />
                    <span>Auto-Check Top {neededCount} Needed</span>
                  </button>
                )}
              </div>
            </div>

            {loadingCandidates ? (
              <div className="p-12 text-center text-xs text-blue-700 flex flex-col items-center justify-center space-y-2">
                <Loader2 className="h-6 w-6 animate-spin text-blue-600" />
                <span>Loading eligible candidates and crew recommendations...</span>
              </div>
            ) : availableCandidates.length === 0 && blockedCandidates.length === 0 ? (
              <div className="p-8 text-center text-xs text-slate-400 bg-slate-50 rounded-xl border border-slate-200">
                No workers found matching grade group {activeJobItem?.planned_grade_code}.
              </div>
            ) : (
              <div className="space-y-3">
                {/* Available Candidates */}
                {availableCandidates.length > 0 ? (
                  <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl max-h-72 overflow-y-auto">
                    {availableCandidates.map((worker) => {
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
                            onChange={() => {}}
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
                              <span className="text-slate-700 font-semibold">
                                {worker.staff_grade_description}
                              </span>

                              {worker.exact_staff_type_match && (
                                <span className="px-1.5 py-0.2 rounded text-[10px] font-bold bg-emerald-100 text-emerald-800">
                                  ✓ Role Match
                                </span>
                              )}

                              {worker.supervisor_name && (
                                <span
                                  className={`px-1.5 py-0.2 rounded text-[10px] font-medium border ${
                                    sharesCrewWithSelected
                                      ? "bg-purple-100 text-purple-800 border-purple-300 font-bold"
                                      : worker.shares_site_group
                                      ? "bg-amber-100 text-amber-800 border-amber-300 font-bold"
                                      : "bg-slate-100 text-slate-600 border-slate-200"
                                  }`}
                                >
                                  Crew: {worker.supervisor_name}
                                </span>
                              )}

                              <span className="text-slate-400">•</span>
                              <span className="text-slate-600">
                                Assigned this week:{" "}
                                <strong>{Number(worker.weekly_allocated_hours).toFixed(1)}h</strong>
                              </span>
                            </div>

                            {/* Reasons Pill Tags */}
                            <div className="flex flex-wrap gap-1 pt-1">
                              {worker.reasons.map((r, i) => (
                                <span
                                  key={i}
                                  className="px-1.5 py-0.5 rounded text-[10px] bg-slate-100 text-slate-600"
                                >
                                  {r}
                                </span>
                              ))}
                            </div>

                            {/* Warnings */}
                            {worker.warnings.length > 0 && (
                              <div className="text-[10px] text-amber-700 flex items-center space-x-1 pt-0.5">
                                <AlertTriangle className="h-3 w-3 shrink-0" />
                                <span>{worker.warnings.join(", ")}</span>
                              </div>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="p-4 text-center text-xs text-slate-500 bg-slate-50 rounded-xl border border-slate-200">
                    No available unblocked workers found with the current filter.
                  </div>
                )}

                {/* Unavailable on this date (PERMANENT Conflicts) */}
                {blockedCandidates.length > 0 && (
                  <div className="space-y-1.5 pt-2">
                    <span className="text-[11px] font-bold text-slate-500 uppercase tracking-wider">
                      Unavailable on {activeDate} ({blockedCandidates.length})
                    </span>
                    <div className="divide-y divide-slate-100 border border-slate-200 rounded-xl bg-slate-50/60 overflow-hidden">
                      {blockedCandidates.map((worker) => (
                        <div
                          key={worker.employee_id}
                          className="p-3 flex items-start space-x-3 text-xs opacity-75 select-none"
                        >
                          <input
                            type="checkbox"
                            disabled
                            className="mt-0.5 rounded text-slate-300 h-4 w-4 shrink-0 cursor-not-allowed"
                          />
                          <div className="flex-1 space-y-0.5">
                            <div className="flex items-center justify-between">
                              <div className="font-bold text-slate-700">
                                {worker.name}{" "}
                                <span className="font-mono text-[11px] text-slate-400 font-normal">
                                  ({worker.tally_id})
                                </span>
                              </div>
                              <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-amber-50 text-amber-800 border border-amber-200">
                                Conflict
                              </span>
                            </div>
                            <p className="text-[11px] text-amber-700 font-medium">
                              {worker.blocked_reason ||
                                "Already assigned to a conflicting job on this date."}
                            </p>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            )}
          </div>

          {/* 3. Standing Team & Sequence Options */}
          <div className="p-4 bg-slate-50 rounded-xl border border-slate-200 space-y-3">
            <div className="flex items-start space-x-3">
              <input
                type="checkbox"
                id="isStandingTeam"
                checked={isStandingTeam}
                onChange={(e) => setIsStandingTeam(e.target.checked)}
                className="mt-1 rounded text-blue-600 focus:ring-blue-500 h-4 w-4"
              />
              <div>
                <label
                  htmlFor="isStandingTeam"
                  className="font-bold text-slate-900 text-xs cursor-pointer flex items-center space-x-1.5"
                >
                  <Layers className="h-3.5 w-3.5 text-blue-600" />
                  <span>Set as Standing Team (13-Month Recurring Schedule)</span>
                </label>
                <p className="text-[11px] text-slate-500 mt-0.5">
                  Materializes daily scheduled work automatically for the next 13 months,
                  preserving worker weekly rest days and public holidays.
                </p>
              </div>
            </div>
          </div>
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex items-center justify-between shrink-0">
          <div className="text-xs text-slate-500">
            {selectedWorkerIds.length > 0 ? (
              <span className="font-semibold text-blue-700">
                {selectedWorkerIds.length} worker(s) selected for assignment
              </span>
            ) : (
              <span>Select workers from the list above to assign</span>
            )}
          </div>

          <div className="flex items-center space-x-3">
            <button
              type="button"
              onClick={onClose}
              disabled={submitting}
              className="px-4 py-2 border border-slate-300 text-slate-700 rounded-xl text-xs font-semibold hover:bg-slate-100 transition"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={handleAssignSubmit}
              disabled={selectedWorkerIds.length === 0 || submitting}
              className="px-5 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 disabled:opacity-50 disabled:cursor-not-allowed flex items-center space-x-2 transition shadow-xs"
            >
              {submitting ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Assigning...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>
                    Assign {selectedWorkerIds.length > 0 ? `(${selectedWorkerIds.length})` : ""}
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
