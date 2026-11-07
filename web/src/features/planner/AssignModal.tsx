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

interface StagedWorker {
  employee_id: string;
  name: string;
  tally_id: string;
  scheduled_work_id?: string;
  standing_assignment_id?: string | null;
  standing_assignment_version?: number | null;
  source?: string;
}

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
  const [initialAssigned, setInitialAssigned] = useState<StagedWorker[]>([]);
  const [stagedWorkers, setStagedWorkers] = useState<StagedWorker[]>([]);
  const [loadingCandidates, setLoadingCandidates] = useState<boolean>(false);
  const [submittingMode, setSubmittingMode] = useState<"SINGLE" | "STANDING" | null>(null);
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

  const requiredCount =
    targetDay !== undefined && targetDay !== null
      ? targetDay.required_staff_count
      : activeJobItem?.required_staff_count || 1;
  const currentStagedCount = stagedWorkers.length;
  const isSlotUnrequired = requiredCount === 0;
  const neededCount = Math.max(0, requiredCount - currentStagedCount);
  const excessCount = isSlotUnrequired ? currentStagedCount : Math.max(0, currentStagedCount - requiredCount);
  const isPeriodicQuotaMet = Boolean(targetDay?.is_quota_met || targetDay?.is_excess);

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
    const existing: StagedWorker[] = (targetDay?.assigned_details || []).map((a: any) => ({
      employee_id: a.employee_id,
      name: a.name,
      tally_id: a.tally_id,
      scheduled_work_id: a.scheduled_work_id,
      standing_assignment_id: a.standing_assignment_id,
      standing_assignment_version: a.standing_assignment_version,
      source: a.source,
    }));

    if (initialWorkerId && !existing.some((e) => e.employee_id === initialWorkerId)) {
      existing.push({
        employee_id: initialWorkerId,
        name: "Selected Worker",
        tally_id: "",
      });
    }

    setInitialAssigned(existing);
    setStagedWorkers(existing);

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

  // Staged workers local management (no automatic server calls)
  const handleRemoveStagedWorker = (empId: string) => {
    setStagedWorkers((prev) => prev.filter((w) => w.employee_id !== empId));
  };

  const handleToggleCandidate = (worker: CandidateRecommendation) => {
    setStagedWorkers((prev) => {
      const exists = prev.some((w) => w.employee_id === worker.employee_id);
      if (exists) {
        return prev.filter((w) => w.employee_id !== worker.employee_id);
      } else {
        return [
          ...prev,
          {
            employee_id: worker.employee_id,
            name: worker.name,
            tally_id: worker.tally_id,
            source: "DIRECT",
          },
        ];
      }
    });
  };

  // Submit handling with explicit Save Current Date or Save Recursively
  const handleSave = async (mode: "SINGLE" | "STANDING") => {
    const jId = activeJobItem?.job_item_id || activeJobItem?.id || initialJobItemId;
    if (!jId) return;

    setSubmittingMode(mode);
    setErrorMsg(null);

    try {
      // 1. Removed workers
      const removed = initialAssigned.filter(
        (orig) => !stagedWorkers.some((s) => s.employee_id === orig.employee_id)
      );

      // 2. Added workers
      const added = stagedWorkers.filter(
        (s) => !initialAssigned.some((orig) => orig.employee_id === s.employee_id)
      );

      if (mode === "SINGLE") {
        // Remove unselected workers for this date only
        for (const rem of removed) {
          if (rem.scheduled_work_id) {
            const delRes = await fetch(`/api/v1/scheduled-work/${rem.scheduled_work_id}`, {
              method: "DELETE",
              headers: authHeaders,
            });
            if (!delRes.ok) {
              const err = await delRes.json().catch(() => ({}));
              throw new Error(err.detail || `Failed to remove worker ${rem.name}`);
            }
          }
        }

        // Add newly selected workers for this date only
        if (added.length > 0) {
          const addRes = await fetch("/api/v1/scheduled-work/batch", {
            method: "POST",
            headers: authHeaders,
            body: JSON.stringify({
              employee_ids: added.map((w) => w.employee_id),
              job_item_id: jId,
              work_date: activeDate,
              assigned_hours: activeJobItem?.hours_per_occurrence,
              as_standing_assignment: false,
              acknowledge_warnings: true,
            }),
          });
          if (!addRes.ok) {
            const err = await addRes.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to assign workers for this date.");
          }
        }
      } else {
        // MODE === "STANDING"
        // 1. Process removed workers
        for (const rem of removed) {
          // If scheduled work exists on current date, delete it
          if (rem.scheduled_work_id) {
            await fetch(`/api/v1/scheduled-work/${rem.scheduled_work_id}`, {
              method: "DELETE",
              headers: authHeaders,
            });
          }

          // If worker has standing assignment, end series as of previous day so current and future dates are cancelled
          if (rem.standing_assignment_id) {
            const prevD = new Date(activeDate);
            prevD.setDate(prevD.getDate() - 1);
            const prevDateStr = prevD.toISOString().split("T")[0];
            const endRes = await fetch(
              `/api/v1/standing-assignments/${rem.standing_assignment_id}/end`,
              {
                method: "POST",
                headers: authHeaders,
                body: JSON.stringify({
                  end_date: prevDateStr,
                  version: rem.standing_assignment_version || 1,
                }),
              }
            );
            if (!endRes.ok) {
              const err = await endRes.json().catch(() => ({}));
              throw new Error(err.detail || `Failed to end standing series for ${rem.name}`);
            }
          }
        }

        // 2. Newly added workers or existing single workers to convert to standing team forward
        const toCreateStanding = stagedWorkers.filter(
          (w) => !w.standing_assignment_id || added.some((a) => a.employee_id === w.employee_id)
        );

        if (toCreateStanding.length > 0) {
          const standingRes = await fetch("/api/v1/scheduled-work/batch", {
            method: "POST",
            headers: authHeaders,
            body: JSON.stringify({
              employee_ids: toCreateStanding.map((w) => w.employee_id),
              job_item_id: jId,
              work_date: activeDate,
              assigned_hours: activeJobItem?.hours_per_occurrence,
              as_standing_assignment: true,
              acknowledge_warnings: true,
            }),
          });
          if (!standingRes.ok) {
            const err = await standingRes.json().catch(() => ({}));
            throw new Error(err.detail || "Failed to set standing team.");
          }
        }
      }

      onSuccess();
      onClose();
    } catch (err: any) {
      setErrorMsg(err.message || "An error occurred while saving assignments.");
    } finally {
      setSubmittingMode(null);
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
  const stagedEmpIds = new Set(stagedWorkers.map((w) => w.employee_id));
  const selectedSupervisors = new Set(
    candidates
      .filter((c) => stagedEmpIds.has(c.employee_id) && c.supervisor_id)
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
            <span className="font-semibold text-slate-600">Slot Staffing:</span>
            <span className="font-bold text-slate-900">
              {currentStagedCount} / {requiredCount} Workers
            </span>
            <span className="text-slate-400">|</span>
            <span
              className={`px-2 py-0.5 rounded-full font-bold ${
                excessCount > 0
                  ? "bg-purple-100 text-purple-800"
                  : neededCount > 0
                  ? "bg-amber-100 text-amber-800"
                  : isSlotUnrequired
                  ? "bg-teal-100 text-teal-800"
                  : "bg-emerald-100 text-emerald-800"
              }`}
            >
              {excessCount > 0
                ? `+${excessCount} Excess worker(s)`
                : neededCount > 0
                ? `${neededCount} worker(s) needed`
                : isSlotUnrequired
                ? "Quota Met / No Requirement"
                : "Fully Staffed"}
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

          {isPeriodicQuotaMet && (
            <div className="p-3 bg-purple-50 border border-purple-200 text-purple-900 rounded-xl text-xs flex items-center space-x-2.5 shadow-2xs">
              <AlertTriangle className="h-4 w-4 shrink-0 text-purple-600" />
              <div>
                <span className="font-bold">Quota Notice: </span>
                <span>
                  The required visits for this {activeJobItem?.frequency_unit ? activeJobItem.frequency_unit.toLowerCase() : "period"} have already been satisfied on other date(s). Any staff assigned to this slot will be recorded as an <strong>Excess Visit</strong>.
                </span>
              </div>
            </div>
          )}

          {(targetDay?.weekday === "SUN" || targetDay?.is_holiday) && (
            <div className="p-3 bg-blue-50 border border-blue-200 text-blue-900 rounded-xl text-xs flex items-center space-x-2.5 shadow-2xs">
              <Zap className="h-4 w-4 shrink-0 text-blue-600" />
              <div>
                <span className="font-bold">Compensatory Shift Tip: </span>
                <span>
                  Use <strong>Save Current Date</strong> for a one-off compensatory shift (e.g. working Sunday to make up for a Friday holiday). Use <strong>Save Recursively</strong> to set the standing team for this week and future weeks.
                </span>
              </div>
            </div>
          )}

          {/* 1. Staged Crew on this Slot */}
          <div className="space-y-2.5 bg-slate-50 p-4 rounded-xl border border-slate-200">
            <div className="flex items-center justify-between">
              <h4 className="text-xs font-bold text-slate-800 uppercase tracking-wider flex items-center gap-1.5">
                <Users className="h-3.5 w-3.5 text-indigo-600" />
                <span>Assigned Crew on this Slot ({stagedWorkers.length})</span>
              </h4>
              <span className="text-[11px] text-slate-500">
                {currentStagedCount === requiredCount
                  ? "Slot requirement fulfilled"
                  : currentStagedCount > requiredCount
                  ? `+${excessCount} Excess worker(s)`
                  : `${neededCount} more worker(s) needed`}
              </span>
            </div>

            {stagedWorkers.length > 0 ? (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 pt-1">
                {stagedWorkers.map((w) => (
                  <div
                    key={w.employee_id}
                    className="p-2.5 rounded-lg border border-slate-200 bg-white flex items-center justify-between text-xs shadow-2xs gap-2"
                  >
                    <div>
                      <div className="font-bold text-slate-900">{w.name}</div>
                      <div className="flex items-center gap-1.5 mt-0.5">
                        <span className="text-[11px] text-slate-500 font-mono">{w.tally_id}</span>
                        {w.standing_assignment_id ? (
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
                    <button
                      type="button"
                      onClick={() => handleRemoveStagedWorker(w.employee_id)}
                      className="p-1 rounded-md text-slate-400 hover:text-red-700 hover:bg-red-50 transition"
                      title="Remove worker from this slot"
                    >
                      <Trash2 className="h-4 w-4" />
                    </button>
                  </div>
                ))}
              </div>
            ) : (
              <div className="py-3 text-center text-xs text-slate-400 border border-dashed border-slate-200 rounded-lg">
                No workers currently staged. Select candidates from the recommendation list below.
              </div>
            )}
          </div>

          {/* 2. Candidate Selection Section */}
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 className="text-xs font-bold text-slate-700 uppercase tracking-wider">
                  Recommended Candidates ({activeJobItem?.staff_grade_description} •{" "}
                  {activeJobItem?.planned_grade_code})
                </h4>
                <p className="text-[11px] text-slate-500">
                  Ranked by exact role match, grade group, and supervisor crew on site
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
                      const unselectedAvailable = availableCandidates.filter(
                        (c) => !stagedEmpIds.has(c.employee_id)
                      );
                      const topToAdd = unselectedAvailable.slice(0, neededCount).map((c) => ({
                        employee_id: c.employee_id,
                        name: c.name,
                        tally_id: c.tally_id,
                        source: "DIRECT",
                      }));
                      setStagedWorkers((prev) => [...prev, ...topToAdd]);
                    }}
                    className="px-3 py-1.5 rounded-lg text-xs font-bold bg-amber-50 text-amber-800 border border-amber-200 hover:bg-amber-100 flex items-center space-x-1.5 transition shadow-2xs"
                  >
                    <Zap className="h-3.5 w-3.5 fill-amber-500 text-amber-600" />
                    <span>Auto-Fill Top {neededCount} Needed</span>
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
                      const isChecked = stagedEmpIds.has(worker.employee_id);
                      const sharesCrewWithSelected =
                        worker.supervisor_id && selectedSupervisors.has(worker.supervisor_id);

                      return (
                        <div
                          key={worker.employee_id}
                          onClick={() => handleToggleCandidate(worker)}
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
        </div>

        {/* Footer Actions */}
        <div className="px-6 py-4 bg-slate-50 border-t border-slate-200 flex flex-wrap items-center justify-between gap-3 shrink-0">
          <div className="text-xs text-slate-500">
            {stagedWorkers.length > 0 ? (
              <span className="font-semibold text-blue-700">
                {stagedWorkers.length} worker(s) staged for slot
              </span>
            ) : (
              <span>No workers currently staged in this slot</span>
            )}
          </div>

          <div className="flex items-center space-x-2.5">
            <button
              type="button"
              onClick={onClose}
              disabled={submittingMode !== null}
              className="px-3.5 py-2 border border-slate-300 text-slate-700 rounded-xl text-xs font-semibold hover:bg-slate-100 transition"
            >
              Cancel
            </button>

            <button
              type="button"
              onClick={() => handleSave("SINGLE")}
              disabled={submittingMode !== null}
              className="px-4 py-2 bg-white border border-blue-600 text-blue-700 rounded-xl text-xs font-bold hover:bg-blue-50 disabled:opacity-50 transition shadow-2xs flex items-center space-x-1.5"
              title="Apply these assignments to this specific date only"
            >
              {submittingMode === "SINGLE" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Saving Date...</span>
                </>
              ) : (
                <>
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  <span>Save Current Date</span>
                </>
              )}
            </button>

            <button
              type="button"
              onClick={() => handleSave("STANDING")}
              disabled={submittingMode !== null}
              className="px-4 py-2 bg-blue-600 text-white rounded-xl text-xs font-bold hover:bg-blue-700 disabled:opacity-50 transition shadow-xs flex items-center space-x-1.5"
              title="Apply as standing team from this date forward (13-month rolling schedule)"
            >
              {submittingMode === "STANDING" ? (
                <>
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  <span>Saving Standing Team...</span>
                </>
              ) : (
                <>
                  <Layers className="h-3.5 w-3.5" />
                  <span>Save Recursively (Standing)</span>
                </>
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
