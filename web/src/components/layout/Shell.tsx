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
  Users,
  UserCheck,
  History,
  LogOut,
  UploadCloud,
  Banknote,
} from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Login } from "../../routes/Login";

interface NavItem {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
}

const navItems: NavItem[] = [
  { label: "Dashboard", to: "/", icon: LayoutDashboard },
  { label: "Employees", to: "/employees", icon: Users, roles: ["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"] },
  { label: "Live Map", to: "/live", icon: MapPin },
  { label: "Planner", to: "/planner", icon: CalendarDays },
  { label: "Attendance", to: "/attendance", icon: Clock },
  { label: "Payroll", to: "/payroll", icon: DollarSign, roles: ["ADMIN", "ENGINEER"] },
  { label: "Salary Structures", to: "/salary-structures", icon: Banknote, roles: ["ADMIN", "ENGINEER"] },
  { label: "Master Data Import", to: "/imports", icon: UploadCloud, roles: ["ADMIN"] },
  { label: "Reports", to: "/reports", icon: FileBarChart },
  { label: "Users & Security", to: "/users", icon: UserCheck, roles: ["ADMIN"] },
  { label: "Audit Logs", to: "/audit-logs", icon: History, roles: ["ADMIN"] },
  { label: "Settings", to: "/settings", icon: SettingsIcon, roles: ["ADMIN", "ENGINEER"] },
];

export const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;
  const { user, isAuthenticated, logout } = useAuth();

  if (!isAuthenticated || user?.must_change_password) {
    return <Login />;
  }

  const allowedNavItems = navItems.filter(
    (item) => !item.roles || (user && item.roles.includes(user.role))
  );

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

        <nav className="flex-1 px-4 py-4 space-y-1 overflow-y-auto">
          {allowedNavItems.map((item) => {
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
              <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block"></span>
              Phase 01 Active
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

            <div className="flex items-center gap-3 pl-4 border-l border-slate-200">
              <div className="text-right">
                <div className="text-xs font-semibold text-slate-800">{user?.username}</div>
                <div className="text-[10px] font-medium text-indigo-600 uppercase tracking-wide">
                  {user?.role}
                </div>
              </div>
              <button
                onClick={logout}
                className="p-1.5 text-slate-400 hover:text-slate-600 rounded-lg hover:bg-slate-100 transition"
                title="Sign out"
              >
                <LogOut className="h-4 w-4" />
              </button>
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
