import React from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import {
  LayoutDashboard,
  MapPin,
  CalendarDays,
  Clock,
  DollarSign,
  FileBarChart,
  Settings as SettingsIcon,
  ShieldCheck,
} from "lucide-react";

interface NavItem {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
}

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard },
  { label: "Live Map", to: "/live", icon: MapPin },
  { label: "Planner", to: "/planner", icon: CalendarDays },
  { label: "Attendance", to: "/attendance", icon: Clock },
  { label: "Payroll", to: "/payroll", icon: DollarSign },
  { label: "Reports", to: "/reports", icon: FileBarChart },
  { label: "Settings", to: "/settings", icon: SettingsIcon },
];

export const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;

  return (
    <div className="flex h-screen w-full bg-slate-50">
      {/* Sidebar */}
      <aside className="w-64 border-r border-slate-200 bg-white flex flex-col">
        <div className="flex h-16 items-center px-6 border-b border-slate-200 gap-3">
          <div className="h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white font-bold">
            FW
          </div>
          <span className="font-semibold text-slate-900 tracking-tight">Field Worker Tracker</span>
        </div>

        <nav className="flex-1 px-4 py-4 space-y-1">
          {navItems.map((item) => {
            const Icon = item.icon;
            const isActive = currentPath === item.to;
            return (
              <Link
                key={item.to}
                to={item.to}
                className={`flex items-center gap-3 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
                  isActive
                    ? "bg-indigo-50 text-indigo-700"
                    : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                }`}
              >
                <Icon className={`h-4 w-4 ${isActive ? "text-indigo-600" : "text-slate-400"}`} />
                {item.label}
              </Link>
            );
          })}
        </nav>

        <div className="p-4 border-t border-slate-200">
          <div className="flex items-center justify-between text-xs text-slate-500">
            <span className="flex items-center gap-1.5">
              <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block animate-pulse"></span>
              Core System Ready
            </span>
            <span className="px-2 py-0.5 rounded bg-slate-100 font-mono text-[10px] text-slate-600">
              v0.1.0
            </span>
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 border-b border-slate-200 bg-white flex items-center justify-between px-8">
          <div className="flex items-center gap-3">
            <h1 className="text-lg font-semibold text-slate-800">
              {navItems.find((item) => item.to === currentPath)?.label || "Field Worker Tracker"}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-medium">
              <ShieldCheck className="h-3.5 w-3.5 text-slate-500" />
              <span>Deployment: <strong>AE</strong> (UAE North)</span>
            </div>
            <div className="h-8 w-8 rounded-full bg-slate-200 flex items-center justify-center text-xs font-semibold text-slate-700">
              AD
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-y-auto p-8">
          {children}
        </main>
      </div>
    </div>
  );
};
