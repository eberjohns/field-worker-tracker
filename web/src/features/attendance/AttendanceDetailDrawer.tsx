import React, { useState, useEffect } from "react";
import {
  X,
  Clock,
  Lock,
  Send,
  ShieldCheck,
  Compass,
} from "lucide-react";
import {
  AttendanceRecord,
  AttendanceCalculationSnapshot,
  TimelineItem,
} from "./types";
import {
  formatDate,
  formatMinutes,
  formatSignedMinutes,
  formatTime,
} from "./formatters";
import { useAuth } from "../../context/AuthContext";

interface AttendanceDetailDrawerProps {
  record: AttendanceRecord | null;
  onClose: () => void;
  onRecordUpdated: () => void;
}

export const AttendanceDetailDrawer: React.FC<AttendanceDetailDrawerProps> = ({
  record,
  onClose,
  onRecordUpdated,
}) => {
  const { token, user } = useAuth();
  const [activeTab, setActiveTab] = useState<
    "overview" | "timeline" | "map" | "versions" | "comments"
  >("overview");

  // Timeline data
  const [timelineItems, setTimelineItems] = useState<TimelineItem[]>([]);
  const [timelineLoading, setTimelineLoading] = useState(false);

  // Version history data
  const [versions, setVersions] = useState<AttendanceCalculationSnapshot[]>([]);
  const [versionsLoading, setVersionsLoading] = useState(false);

  // Add Comment Form
  const [commentType, setCommentType] = useState<string>("GENERAL");
  const [commentText, setCommentText] = useState<string>("");
  const [submittingComment, setSubmittingComment] = useState(false);

  // Decision Form
  const [decisionComment, setDecisionComment] = useState<string>("");
  const [submittingDecision, setSubmittingDecision] = useState(false);
  const [decisionError, setDecisionError] = useState<string | null>(null);

  useEffect(() => {
    if (!record) return;

    if (activeTab === "timeline") {
      fetchTimeline();
    } else if (activeTab === "versions") {
      fetchVersions();
    }
  }, [record?.id, activeTab]);

  if (!record) return null;

  const calc = record.current_calculation;
  const isSupervisorOrEngineer = ["SUPERVISOR", "ENGINEER", "ADMIN"].includes(user?.role || "");

  const fetchTimeline = async () => {
    setTimelineLoading(true);
    try {
      const res = await fetch(`/api/v1/attendance/${record.id}/timeline`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setTimelineItems(data.timeline_items || []);
      }
    } catch (err) {
      console.error("Failed to load timeline", err);
    } finally {
      setTimelineLoading(false);
    }
  };

  const fetchVersions = async () => {
    setVersionsLoading(true);
    try {
      const res = await fetch(`/api/v1/attendance/${record.id}/calculations`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (res.ok) {
        const data = await res.json();
        setVersions(data || []);
      }
    } catch (err) {
      console.error("Failed to load versions", err);
    } finally {
      setVersionsLoading(false);
    }
  };

  const handleAddComment = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!commentText.trim()) return;

    setSubmittingComment(true);
    try {
      const res = await fetch(`/api/v1/attendance/${record.id}/comments`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          comment_type: commentType,
          comment_text: commentText.trim(),
        }),
      });
      if (res.ok) {
        setCommentText("");
        onRecordUpdated();
      }
    } catch (err) {
      console.error("Failed to post comment", err);
    } finally {
      setSubmittingComment(false);
    }
  };

  const handleRecordDecision = async (decision: "APPROVED" | "REJECTED") => {
    if (decision === "REJECTED" && !decisionComment.trim()) {
      setDecisionError("A justification comment is required when rejecting attendance.");
      return;
    }
    setDecisionError(null);
    setSubmittingDecision(true);
    try {
      const res = await fetch(`/api/v1/attendance/${record.id}/decisions`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({
          decision,
          comment: decisionComment.trim() || undefined,
        }),
      });
      if (res.ok) {
        setDecisionComment("");
        onRecordUpdated();
      } else {
        const errData = await res.json();
        setDecisionError(errData.detail || "Failed to record approval decision.");
      }
    } catch (err) {
      setDecisionError("Network error recording decision.");
    } finally {
      setSubmittingDecision(false);
    }
  };

  return (
    <div className="fixed inset-y-0 right-0 w-full max-w-2xl bg-white shadow-2xl border-l border-slate-200 z-50 flex flex-col">
      {/* Header */}
      <div className="p-4 border-b border-slate-200 flex items-center justify-between bg-slate-50">
        <div>
          <div className="flex items-center gap-2">
            <h2 className="text-base font-semibold text-slate-900">{record.employee_name}</h2>
            <span className="font-mono text-xs px-2 py-0.5 rounded bg-slate-200 text-slate-700">
              {record.tally_id}
            </span>
            {record.locked && (
              <span className="inline-flex items-center gap-1 text-[11px] font-medium px-2 py-0.5 rounded bg-amber-100 text-amber-800">
                <Lock className="h-3 w-3" /> Locked (Payroll)
              </span>
            )}
          </div>
          <div className="text-xs text-slate-500 mt-0.5">
            Work Date: <span className="font-medium text-slate-700">{formatDate(record.work_date)}</span>
          </div>
        </div>
        <button
          onClick={onClose}
          className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-200/50"
        >
          <X className="h-5 w-5" />
        </button>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-slate-200 bg-white text-xs font-medium">
        <button
          onClick={() => setActiveTab("overview")}
          className={`flex-1 py-3 px-3 text-center border-b-2 transition-colors ${
            activeTab === "overview"
              ? "border-emerald-600 text-emerald-700 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Overview
        </button>
        <button
          onClick={() => setActiveTab("timeline")}
          className={`flex-1 py-3 px-3 text-center border-b-2 transition-colors ${
            activeTab === "timeline"
              ? "border-emerald-600 text-emerald-700 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Timeline
        </button>
        <button
          onClick={() => setActiveTab("versions")}
          className={`flex-1 py-3 px-3 text-center border-b-2 transition-colors ${
            activeTab === "versions"
              ? "border-emerald-600 text-emerald-700 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Versions ({calc?.version_no ?? 1})
        </button>
        <button
          onClick={() => setActiveTab("comments")}
          className={`flex-1 py-3 px-3 text-center border-b-2 transition-colors ${
            activeTab === "comments"
              ? "border-emerald-600 text-emerald-700 font-semibold"
              : "border-transparent text-slate-500 hover:text-slate-700"
          }`}
        >
          Review & Comments ({record.comments.length})
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-5 space-y-6 text-xs">
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* KPI Cards */}
            <div className="grid grid-cols-3 gap-3">
              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Worked Time</div>
                <div className="text-xl font-mono font-bold text-slate-900 mt-1">
                  {formatMinutes(calc?.worked_minutes)}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Req: {formatMinutes(calc?.required_minutes)}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Variation</div>
                <div
                  className={`text-xl font-mono font-bold mt-1 ${
                    (calc?.variation_minutes ?? 0) < 0
                      ? "text-rose-600"
                      : (calc?.variation_minutes ?? 0) > 0
                      ? "text-emerald-600"
                      : "text-slate-900"
                  }`}
                >
                  {formatSignedMinutes(calc?.variation_minutes)}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Grace: {calc?.grace_minutes ?? 10}m {calc?.grace_applied ? "(applied)" : ""}
                </div>
              </div>

              <div className="p-3 rounded-lg bg-slate-50 border border-slate-200">
                <div className="text-[11px] text-slate-500 uppercase font-semibold">Shift Span</div>
                <div className="text-xl font-mono font-bold text-slate-900 mt-1">
                  {formatMinutes(calc?.shift_span_minutes)}
                </div>
                <div className="text-[11px] text-slate-500 mt-0.5">
                  Planned: {formatMinutes(calc?.planned_total_minutes)}
                </div>
              </div>
            </div>

            {/* Overtime & Day Classification */}
            <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
              <h3 className="font-semibold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                <Clock className="h-4 w-4 text-emerald-600" /> Overtime & Day Type
              </h3>
              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <div className="text-[10px] text-slate-500">Day Type</div>
                  <div className="font-semibold text-slate-800 font-mono mt-0.5">{calc?.day_type}</div>
                </div>
                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <div className="text-[10px] text-slate-500">Standard Hours</div>
                  <div className="font-semibold text-slate-800 font-mono mt-0.5">
                    {formatMinutes(calc?.standard_hours_minutes)}
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <div className="text-[10px] text-slate-500">OT1 (Normal)</div>
                  <div className="font-semibold text-emerald-700 font-mono mt-0.5">
                    {formatMinutes(calc?.ot1_minutes)}
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-50 border border-slate-100">
                  <div className="text-[10px] text-slate-500">OT2 (Holiday/Sun)</div>
                  <div className="font-semibold text-emerald-700 font-mono mt-0.5">
                    {formatMinutes(calc?.ot2_minutes)}
                  </div>
                </div>
              </div>
            </div>

            {/* Movement breakdown */}
            <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-3">
              <h3 className="font-semibold text-slate-800 text-xs uppercase tracking-wider flex items-center gap-1.5">
                <Compass className="h-4 w-4 text-blue-600" /> Movement Breakdown (DEC-28)
              </h3>
              <div className="grid grid-cols-4 gap-2 text-center">
                <div className="p-2 rounded bg-emerald-50 border border-emerald-100">
                  <div className="text-[10px] text-emerald-700 font-medium">Productive</div>
                  <div className="font-mono font-bold text-emerald-900 mt-0.5">
                    {formatMinutes(calc?.productive_minutes)}
                  </div>
                </div>
                <div className="p-2 rounded bg-blue-50 border border-blue-100">
                  <div className="text-[10px] text-blue-700 font-medium">Transit</div>
                  <div className="font-mono font-bold text-blue-900 mt-0.5">
                    {formatMinutes(calc?.transit_minutes)}
                  </div>
                </div>
                <div className="p-2 rounded bg-purple-50 border border-purple-100">
                  <div className="text-[10px] text-purple-700 font-medium">Offsite</div>
                  <div className="font-mono font-bold text-purple-900 mt-0.5">
                    {formatMinutes(calc?.offsite_minutes)}
                  </div>
                </div>
                <div className="p-2 rounded bg-slate-50 border border-slate-200">
                  <div className="text-[10px] text-slate-600 font-medium">Idle</div>
                  <div className="font-mono font-bold text-slate-800 mt-0.5">
                    {formatMinutes(calc?.idle_minutes)}
                  </div>
                </div>
              </div>
            </div>

            {/* Review Reasons & Flags */}
            <div className="p-4 rounded-xl border border-slate-200 bg-white space-y-2">
              <div className="text-xs font-semibold text-slate-800">Review Reasons & Anomaly Flags</div>
              <div className="flex flex-wrap gap-1.5">
                {calc?.review_reasons?.map((reason, idx) => (
                  <span
                    key={idx}
                    className="px-2 py-1 text-xs font-medium rounded-md bg-amber-50 text-amber-800 border border-amber-200"
                  >
                    {reason}
                  </span>
                ))}
                {calc?.flags?.map((flag, idx) => (
                  <span
                    key={`flag-${idx}`}
                    className="px-2 py-1 text-xs font-mono rounded-md bg-slate-100 text-slate-700 border border-slate-200"
                  >
                    {flag}
                  </span>
                ))}
                {(!calc?.review_reasons || calc.review_reasons.length === 0) &&
                  (!calc?.flags || calc.flags.length === 0) && (
                    <span className="text-slate-400 italic">No anomalies or review flags.</span>
                  )}
              </div>
            </div>

            {/* Immutability & Calculation Provenance */}
            <div className="p-3 rounded-lg bg-slate-50 border border-slate-200 text-slate-500 font-mono text-[11px] space-y-1">
              <div>Version: v{calc?.version_no} (Engine {calc?.engine_version})</div>
              <div>Input Hash: {calc?.input_hash}</div>
              <div>Calculated: {calc?.calculated_at}</div>
              <div>Reason: {calc?.reason}</div>
            </div>
          </div>
        )}

        {activeTab === "timeline" && (
          <div className="space-y-4">
            {timelineLoading ? (
              <div className="p-8 text-center text-slate-400">Loading timeline...</div>
            ) : timelineItems.length === 0 ? (
              <div className="p-8 text-center text-slate-400">No events or visits recorded for this day.</div>
            ) : (
              <div className="relative pl-6 space-y-4 before:absolute before:left-2.5 before:top-2 before:bottom-2 before:w-0.5 before:bg-slate-200">
                {timelineItems.map((item, idx) => {
                  const itemId = item.item_id || item.id || `timeline-${idx}`;
                  const title = item.label || item.title || item.item_type || "Timeline Item";
                  const place = item.place_name || item.description || "";
                  const startTime = item.started_at || item.timestamp;
                  const endTime = item.ended_at;
                  const lat = item.details?.latitude ?? item.latitude;
                  const lng = item.details?.longitude ?? item.longitude;

                  return (
                    <div key={itemId} className="relative">
                      <div className="absolute -left-6 top-1 h-3 w-3 rounded-full bg-emerald-600 border-2 border-white ring-2 ring-slate-100" />
                      <div className="p-3 rounded-lg border border-slate-200 bg-white space-y-1">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold text-slate-900">{title}</span>
                          <span className="font-mono text-slate-500">
                            {formatTime(startTime)}
                            {endTime && endTime !== startTime ? ` - ${formatTime(endTime)}` : ""}
                          </span>
                        </div>
                        {place && <p className="text-slate-600 text-xs">{place}</p>}
                        <div className="flex items-center gap-2 pt-1 text-xs text-slate-500">
                          {item.duration_minutes > 0 && (
                            <span>Duration: {formatMinutes(item.duration_minutes)}</span>
                          )}
                          {item.is_inferred && (
                            <span className="px-1.5 py-0.5 text-[10px] font-medium rounded bg-amber-100 text-amber-800">
                              Inferred Exit
                            </span>
                          )}
                        </div>
                        {lat != null && lng != null && (
                          <div className="text-[10px] text-slate-400 font-mono">
                            Coordinates: {Number(lat).toFixed(5)}, {Number(lng).toFixed(5)}
                          </div>
                        )}
                        {item.flags && item.flags.length > 0 && (
                          <div className="flex flex-wrap gap-1 pt-1">
                            {item.flags.map((f, fIdx) => (
                              <span
                                key={fIdx}
                                className="px-1.5 py-0.5 text-[10px] font-mono rounded bg-slate-100 text-slate-600 border border-slate-200"
                              >
                                {f}
                              </span>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {activeTab === "versions" && (
          <div className="space-y-3">
            {versionsLoading ? (
              <div className="p-8 text-center text-slate-400">Loading versions...</div>
            ) : versions.length === 0 ? (
              <div className="p-8 text-center text-slate-400">Only initial calculation recorded.</div>
            ) : (
              versions.map((ver) => (
                <div key={ver.id} className="p-3 rounded-lg border border-slate-200 bg-white space-y-2">
                  <div className="flex items-center justify-between">
                    <span className="font-semibold text-slate-900">
                      Version {ver.version_no} {ver.id === calc?.id ? "(Current)" : ""}
                    </span>
                    <span className="text-[11px] text-slate-500 font-mono">
                      {new Date(ver.calculated_at).toLocaleString()}
                    </span>
                  </div>
                  <div className="grid grid-cols-3 gap-2 text-center text-[11px] font-mono">
                    <div className="p-1 rounded bg-slate-50">Worked: {formatMinutes(ver.worked_minutes)}</div>
                    <div className="p-1 rounded bg-slate-50">Var: {formatSignedMinutes(ver.variation_minutes)}</div>
                    <div className="p-1 rounded bg-slate-50">Status: {ver.business_status}</div>
                  </div>
                  <div className="text-[10px] text-slate-400 font-mono truncate">
                    Hash: {ver.input_hash} | Reason: {ver.reason}
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "comments" && (
          <div className="space-y-6">
            {/* Approval Decision Box (Supervisors / Engineers) */}
            {isSupervisorOrEngineer && !record.locked && (
              <div className="p-4 rounded-xl border border-slate-200 bg-slate-50 space-y-3">
                <div className="flex items-center justify-between">
                  <h4 className="font-semibold text-slate-900 text-xs flex items-center gap-1.5">
                    <ShieldCheck className="h-4 w-4 text-emerald-600" /> Review Decision
                  </h4>
                  <span className="text-slate-500 text-[11px]">Current: {record.review_status}</span>
                </div>

                {decisionError && (
                  <div className="p-2 rounded bg-rose-50 border border-rose-200 text-rose-700 text-xs">
                    {decisionError}
                  </div>
                )}

                <textarea
                  value={decisionComment}
                  onChange={(e) => setDecisionComment(e.target.value)}
                  placeholder="Decision comment / explanation (required for rejection)..."
                  className="w-full p-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-emerald-500"
                  rows={2}
                />

                <div className="flex items-center gap-2 justify-end">
                  <button
                    type="button"
                    onClick={() => handleRecordDecision("REJECTED")}
                    disabled={submittingDecision}
                    className="px-3 py-1.5 rounded-lg border border-rose-200 text-rose-700 bg-rose-50 hover:bg-rose-100 font-medium transition-colors"
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    onClick={() => handleRecordDecision("APPROVED")}
                    disabled={submittingDecision}
                    className="px-3 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-700 text-white font-medium transition-colors"
                  >
                    Approve
                  </button>
                </div>
              </div>
            )}

            {/* Existing Comments */}
            <div className="space-y-3">
              <h4 className="font-semibold text-slate-800 text-xs">Activity & Explanations</h4>
              {record.comments.length === 0 ? (
                <div className="text-slate-400 italic">No comments or explanations submitted yet.</div>
              ) : (
                record.comments.map((c) => (
                  <div key={c.id} className="p-3 rounded-lg border border-slate-200 bg-white space-y-1">
                    <div className="flex items-center justify-between">
                      <span className="font-semibold text-slate-900">{c.author_name}</span>
                      <span className="text-[10px] text-slate-400 font-mono">
                        {new Date(c.created_at).toLocaleString()}
                      </span>
                    </div>
                    <div className="inline-block px-1.5 py-0.5 text-[9px] font-semibold rounded bg-slate-100 text-slate-600 mb-1">
                      {c.comment_type}
                    </div>
                    <p className="text-slate-700">{c.comment_text}</p>
                  </div>
                ))
              )}
            </div>

            {/* Post new comment */}
            <form onSubmit={handleAddComment} className="space-y-3 pt-3 border-t border-slate-200">
              <h4 className="font-semibold text-slate-800 text-xs">Add Explanation or Comment</h4>
              <div className="flex gap-2">
                <select
                  value={commentType}
                  onChange={(e) => setCommentType(e.target.value)}
                  className="p-2 border border-slate-300 rounded-lg text-xs bg-white"
                >
                  <option value="GENERAL">General</option>
                  <option value="EXPLANATION">Explanation</option>
                  <option value="ATTENDANCE_CORRECTION">Correction Request</option>
                </select>
                <input
                  type="text"
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="Explain late arrival, site variance, or attach gate pass reference..."
                  className="flex-1 p-2 border border-slate-300 rounded-lg text-xs focus:ring-1 focus:ring-emerald-500"
                />
                <button
                  type="submit"
                  disabled={submittingComment || !commentText.trim()}
                  className="px-3 py-2 bg-slate-900 hover:bg-slate-800 text-white rounded-lg flex items-center gap-1 font-medium disabled:opacity-50"
                >
                  <Send className="h-3.5 w-3.5" />
                  Post
                </button>
              </div>
            </form>
          </div>
        )}
      </div>
    </div>
  );
};
