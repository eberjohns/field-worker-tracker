import React from "react";
import {
  formatDate,
  formatMinutes,
  formatSignedMinutes,
  formatTime,
} from "./formatters";
import { AttendanceRecord } from "./types";
import {
  CheckCircle2,
  AlertTriangle,
  XCircle,
  MessageSquare,
  Lock,
} from "lucide-react";

interface AttendanceTableProps {
  records: AttendanceRecord[];
  loading: boolean;
  onSelectRecord: (record: AttendanceRecord) => void;
}

export const AttendanceTable: React.FC<AttendanceTableProps> = ({
  records,
  loading,
  onSelectRecord,
}) => {
  if (loading) {
    return (
      <div className="p-12 text-center text-slate-500 bg-white rounded-xl border border-slate-200">
        <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-emerald-600 mx-auto mb-3" />
        Loading attendance records...
      </div>
    );
  }

  if (records.length === 0) {
    return (
      <div className="p-12 text-center text-slate-500 bg-white rounded-xl border border-slate-200">
        No attendance records found for this period.
      </div>
    );
  }

  const getReviewChipColor = (reason: string) => {
    switch (reason) {
      case "Short hours":
      case "Mock location":
        return "bg-rose-50 text-rose-700 border-rose-200";
      case "Estimated exit":
      case "Tracking off":
        return "bg-amber-50 text-amber-700 border-amber-200";
      case "Overtime":
        return "bg-emerald-50 text-emerald-700 border-emerald-200";
      case "Other site":
        return "bg-purple-50 text-purple-700 border-purple-200";
      case "Unscheduled work":
        return "bg-blue-50 text-blue-700 border-blue-200";
      default:
        return "bg-slate-100 text-slate-700 border-slate-200";
    }
  };

  const getStatusBadge = (status: string) => {
    switch (status) {
      case "PRESENT":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-emerald-100 text-emerald-800">Present</span>;
      case "PARTIAL":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-amber-100 text-amber-800">Partial</span>;
      case "ABSENT":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-rose-100 text-rose-800">Absent</span>;
      case "REST":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-100 text-slate-700">Rest</span>;
      case "ON_LEAVE":
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-sky-100 text-sky-800">On Leave</span>;
      default:
        return <span className="px-2 py-0.5 text-xs font-semibold rounded bg-slate-100 text-slate-700">{status}</span>;
    }
  };

  const getReviewStatusBadge = (status: string) => {
    switch (status) {
      case "APPROVED":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-emerald-700">
            <CheckCircle2 className="h-3.5 w-3.5" /> Approved
          </span>
        );
      case "REJECTED":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-rose-700">
            <XCircle className="h-3.5 w-3.5" /> Rejected
          </span>
        );
      case "PENDING_REVIEW":
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-amber-700">
            <AlertTriangle className="h-3.5 w-3.5" /> Needs Review
          </span>
        );
      default:
        return (
          <span className="inline-flex items-center gap-1 text-xs font-medium text-slate-500">
            <CheckCircle2 className="h-3.5 w-3.5 text-slate-400" /> Auto
          </span>
        );
    }
  };

  return (
    <div className="bg-white rounded-xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-left text-xs border-collapse">
          <thead>
            {/* Top Header Grouping */}
            <tr className="bg-slate-50 text-slate-600 border-b border-slate-200 font-semibold uppercase tracking-wider">
              <th colSpan={2} className="py-2.5 px-3 border-r border-slate-200">
                Worker
              </th>
              <th colSpan={7} className="py-2.5 px-3 text-center border-r border-slate-200 bg-slate-100/60">
                Planned Schedule
              </th>
              <th colSpan={7} className="py-2.5 px-3 text-center border-r border-slate-200 bg-slate-50">
                Actual Measured
              </th>
              <th colSpan={2} className="py-2.5 px-3 text-center border-r border-slate-200 bg-slate-100/60">
                Variation (Act - Plan)
              </th>
              <th colSpan={2} className="py-2.5 px-3 text-center">
                Review & Workflow
              </th>
            </tr>
            {/* Sub-header columns */}
            <tr className="bg-slate-100 text-slate-500 border-b border-slate-200 font-medium">
              <th className="py-2 px-3">Name / Tally ID</th>
              <th className="py-2 px-3 border-r border-slate-200">Date</th>

              {/* Planned */}
              <th className="py-2 px-2 text-center">Acc.st</th>
              <th className="py-2 px-2 text-center">First</th>
              <th className="py-2 px-2 text-center">Break</th>
              <th className="py-2 px-2 text-center">Last</th>
              <th className="py-2 px-2 text-center">Acc.end</th>
              <th className="py-2 px-2 text-center font-semibold text-slate-700">Total</th>
              <th className="py-2 px-2 text-center font-semibold text-slate-700 border-r border-slate-200">Worked</th>

              {/* Actual */}
              <th className="py-2 px-2 text-center">Acc.st</th>
              <th className="py-2 px-2 text-center">First</th>
              <th className="py-2 px-2 text-center">Break</th>
              <th className="py-2 px-2 text-center">Last</th>
              <th className="py-2 px-2 text-center">Acc.end</th>
              <th className="py-2 px-2 text-center font-semibold text-slate-700">Total</th>
              <th className="py-2 px-2 text-center font-semibold text-slate-700 border-r border-slate-200">Worked</th>

              {/* Variation */}
              <th className="py-2 px-2 text-center font-semibold text-slate-700">Var.total</th>
              <th className="py-2 px-2 text-center font-semibold text-slate-700 border-r border-slate-200">Var.worked</th>

              {/* Status & Review */}
              <th className="py-2 px-3">Status / Flags</th>
              <th className="py-2 px-3 text-center">Approval</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-100">
            {records.map((rec) => {
              const calc = rec.current_calculation;
              const hasAcc = calc ? calc.inputs_snapshot?.has_accommodation ?? true : true;
              const varTotal = calc ? calc.shift_span_minutes - calc.planned_total_minutes : 0;
              const varWorked = calc ? calc.variation_minutes : 0;

              return (
                <tr
                  key={rec.id}
                  onClick={() => onSelectRecord(rec)}
                  className="hover:bg-slate-50/80 cursor-pointer transition-colors"
                >
                  {/* Worker Name & ID */}
                  <td className="py-2.5 px-3">
                    <div className="font-medium text-slate-900 flex items-center gap-1.5">
                      {rec.locked && (
                        <span title="Locked by Approved Payroll">
                          <Lock className="h-3 w-3 text-amber-500" />
                        </span>
                      )}
                      {rec.employee_name}
                    </div>
                    <div className="text-[11px] text-slate-500 font-mono">{rec.tally_id}</div>
                  </td>

                  {/* Work Date */}
                  <td className="py-2.5 px-3 border-r border-slate-200 text-slate-700 whitespace-nowrap">
                    {formatDate(rec.work_date)}
                  </td>

                  {/* Planned */}
                  <td className="py-2.5 px-2 text-center text-slate-600 font-mono">
                    {hasAcc ? formatTime(calc?.planned_accommodation_departure) : "n/a"}
                  </td>
                  <td className="py-2.5 px-2 text-center text-slate-600 font-mono">
                    {formatTime(calc?.planned_first_site_start)}
                  </td>
                  <td className="py-2.5 px-2 text-center text-slate-500 font-mono">
                    {calc?.planned_break_minutes ? `${calc.planned_break_minutes}m` : "-"}
                  </td>
                  <td className="py-2.5 px-2 text-center text-slate-600 font-mono">
                    {formatTime(calc?.planned_last_site_end)}
                  </td>
                  <td className="py-2.5 px-2 text-center text-slate-600 font-mono">
                    {hasAcc ? formatTime(calc?.planned_accommodation_return) : "n/a"}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono font-medium text-slate-800 bg-slate-50/50">
                    {formatMinutes(calc?.planned_total_minutes)}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono font-medium text-slate-800 border-r border-slate-200 bg-slate-50/50">
                    {formatMinutes(calc?.planned_worked_minutes)}
                  </td>

                  {/* Actual */}
                  <td className="py-2.5 px-2 text-center font-mono text-slate-800">
                    {hasAcc ? formatTime(calc?.accommodation_departure_at) : "n/a"}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono text-slate-800">
                    {formatTime(calc?.first_site_entry_at)}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono text-slate-600">
                    {calc ? `${calc.break_minutes_used}m` : "-"}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono text-slate-800">
                    {formatTime(calc?.last_site_exit_at)}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono text-slate-800">
                    {hasAcc ? formatTime(calc?.accommodation_return_at) : "n/a"}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono font-semibold text-slate-900 bg-slate-50/50">
                    {formatMinutes(calc?.shift_span_minutes)}
                  </td>
                  <td className="py-2.5 px-2 text-center font-mono font-semibold text-slate-900 border-r border-slate-200 bg-slate-50/50">
                    {formatMinutes(calc?.worked_minutes)}
                  </td>

                  {/* Variation */}
                  <td
                    className={`py-2.5 px-2 text-center font-mono font-medium ${
                      varTotal < 0 ? "text-rose-600 font-semibold" : varTotal > 0 ? "text-emerald-600" : "text-slate-600"
                    }`}
                  >
                    {formatSignedMinutes(varTotal)}
                  </td>
                  <td
                    className={`py-2.5 px-2 text-center font-mono font-medium border-r border-slate-200 ${
                      varWorked < 0 ? "text-rose-600 font-semibold" : varWorked > 0 ? "text-emerald-600" : "text-slate-600"
                    }`}
                  >
                    {formatSignedMinutes(varWorked)}
                  </td>

                  {/* Status / Review chips */}
                  <td className="py-2.5 px-3">
                    <div className="flex items-center gap-1.5 flex-wrap">
                      {getStatusBadge(rec.business_status)}
                      {calc?.review_reasons?.map((reason, idx) => (
                        <span
                          key={idx}
                          className={`px-1.5 py-0.5 text-[10px] font-medium rounded border ${getReviewChipColor(
                            reason
                          )}`}
                        >
                          {reason}
                        </span>
                      ))}
                      {rec.comments.length > 0 && (
                        <span className="inline-flex items-center gap-0.5 text-[11px] text-slate-500 ml-1">
                          <MessageSquare className="h-3 w-3" />
                          {rec.comments.length}
                        </span>
                      )}
                    </div>
                  </td>

                  {/* Approval Status */}
                  <td className="py-2.5 px-3 text-center whitespace-nowrap">
                    {getReviewStatusBadge(rec.review_status)}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
};
