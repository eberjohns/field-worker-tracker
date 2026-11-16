import React, { useState } from "react";
import { FileBarChart, History } from "lucide-react";
import { ReportsHub } from "../features/reports/ReportsHub";
import { GeneratedReports } from "../features/reports/GeneratedReports";

interface ReportsProps {
  initialTab?: "hub" | "generated";
}

export const Reports: React.FC<ReportsProps> = ({ initialTab = "hub" }) => {
  const [activeTab, setActiveTab] = useState<"hub" | "generated">(initialTab);

  return (
    <div className="space-y-6">
      {/* Top Navigation Tabs */}
      <div className="flex items-center justify-between border-b border-slate-200">
        <div className="flex space-x-8">
          <button
            onClick={() => setActiveTab("hub")}
            className={`flex items-center gap-2 pb-3 px-1 text-sm font-semibold border-b-2 transition ${
              activeTab === "hub"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            }`}
          >
            <FileBarChart className="w-4 h-4" />
            <span>Reports Hub</span>
          </button>
          <button
            onClick={() => setActiveTab("generated")}
            className={`flex items-center gap-2 pb-3 px-1 text-sm font-semibold border-b-2 transition ${
              activeTab === "generated"
                ? "border-blue-600 text-blue-600"
                : "border-transparent text-slate-500 hover:text-slate-700 hover:border-slate-300"
            }`}
          >
            <History className="w-4 h-4" />
            <span>Generated Reports Archive</span>
          </button>
        </div>
      </div>

      {/* Tab Content */}
      {activeTab === "hub" ? <ReportsHub /> : <GeneratedReports />}
    </div>
  );
};
