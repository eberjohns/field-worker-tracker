import React from "react";
import { CalendarDays } from "lucide-react";

export const Planner: React.FC = () => {
  return (
    <div className="p-12 text-center bg-white rounded-xl border border-slate-200 shadow-sm space-y-4">
      <div className="mx-auto h-12 w-12 rounded-full bg-slate-100 flex items-center justify-center text-slate-500">
        <CalendarDays className="h-6 w-6" />
      </div>
      <h3 className="text-lg font-medium text-slate-900">Weekly Roster & Yearly Plan</h3>
      <p className="text-sm text-slate-500 max-w-md mx-auto">
        Scheduled for milestone implementation (Phase 05).
      </p>
    </div>
  );
};
