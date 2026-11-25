import React, { useState, useEffect } from "react";
import { Link, useRouterState } from "@tanstack/react-router";
import { LogOut, Menu, PanelLeftClose, PanelLeftOpen, ShieldCheck } from "lucide-react";
import { useAuth } from "../../context/AuthContext";
import { Login } from "../../routes/Login";
import { APP_VERSION } from "../../version";
import { ScrollArea } from "../../ui";
import { isNavItemActive, navForRole, pageTitle } from "./nav";

const COLLAPSED_KEY = "fwt_sidebar_collapsed";
/** Below this width the sidebar is a drawer opened from the top bar (phones, small tablets). */
const NARROW_QUERY = "(max-width: 767px)";

function useIsNarrow(): boolean {
  const [narrow, setNarrow] = useState(() =>
    typeof window !== "undefined" && typeof window.matchMedia === "function" ? window.matchMedia(NARROW_QUERY).matches : false,
  );
  useEffect(() => {
    if (typeof window.matchMedia !== "function") return;
    const mq = window.matchMedia(NARROW_QUERY);
    const onChange = () => setNarrow(mq.matches);
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return narrow;
}

export const Shell: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const routerState = useRouterState();
  const currentPath = routerState.location.pathname;
  const currentSearch = (routerState.location.search ?? {}) as Record<string, unknown>;
  const currentHash = routerState.location.hash;
  const title = pageTitle(currentPath, currentSearch);

  useEffect(() => {
    document.title = title === "Field Worker Tracker" ? title : `${title} · Field Worker Tracker`;
  }, [title]);
  const { user, isAuthenticated, logout } = useAuth();

  const [isCollapsed, setIsCollapsed] = useState<boolean>(() => {
    try {
      return localStorage.getItem(COLLAPSED_KEY) === "true";
    } catch {
      return false;
    }
  });

  const toggleSidebar = () => {
    setIsCollapsed((prev) => {
      const next = !prev;
      try {
        localStorage.setItem(COLLAPSED_KEY, String(next));
      } catch (err) {
        console.warn("Failed to persist sidebar state to localStorage", err);
      }
      return next;
    });
  };

  const isNarrow = useIsNarrow();
  const [drawerOpen, setDrawerOpen] = useState(false);
  // The drawer closes when a menu item is chosen (the path changes).
  useEffect(() => setDrawerOpen(false), [currentPath, currentHash]);
  // On a narrow screen the drawer always shows labels; collapsing is a desktop choice.
  const collapsed = isCollapsed && !isNarrow;

  const [pendingApprovalsCount, setPendingApprovalsCount] = useState<number>(0);

  useEffect(() => {
    const token = localStorage.getItem("fwt_token");
    if (
      !token ||
      (user?.role !== "ADMIN" && user?.role !== "ENGINEER" && user?.role !== "SUPERINTENDENT")
    )
      return;
    const fetchCounts = async () => {
      try {
        const res = await fetch("/api/v1/approvals/counts", {
          headers: { Authorization: `Bearer ${token}` },
        });
        if (res.ok) {
          const data = await res.json();
          setPendingApprovalsCount(data?.total || 0);
        }
      } catch (err) {
        console.error("Failed to fetch pending approvals count", err);
      }
    };
    fetchCounts();
    const timer = setInterval(fetchCounts, 30000);
    return () => clearInterval(timer);
  }, [user]);

  // The component gallery (/dev/ui) has no data, so it needs neither sign-in nor the sidebar.
  if (import.meta.env.DEV && currentPath.startsWith("/dev/")) {
    return <>{children}</>;
  }

  if (!isAuthenticated || user?.must_change_password) {
    return <Login />;
  }

  const groups = navForRole(user?.role);

  return (
    <div className="flex h-screen w-full bg-slate-50 overflow-hidden">
      {/* Sidebar */}
      {isNarrow && drawerOpen && (
        <div
          className="fixed inset-0 z-30 bg-slate-900/40" /* ui-rules-allow: the phone menu's backdrop, not a dialog */
          aria-hidden
          onClick={() => setDrawerOpen(false)}
        />
      )}
      <aside
        id="app-sidebar"
        className={`${collapsed ? "w-16" : "w-64"} border-r border-slate-200 bg-white flex flex-col transition-all duration-200 shrink-0 select-none z-40 ${
          isNarrow ? `fixed inset-y-0 left-0 shadow-xl ${drawerOpen ? "translate-x-0" : "-translate-x-full"}` : ""
        }`}
        aria-hidden={isNarrow && !drawerOpen ? true : undefined}
      >
        {/* Logo: never covered; the collapse button lives in the footer */}
        <Link
          to="/"
          className={`flex h-16 items-center gap-2.5 border-b border-slate-200 overflow-hidden shrink-0 ${
            collapsed ? "justify-center px-2" : "px-4"
          }`}
          title="Field Worker Tracker"
        >
          <img src="/favicon.svg" alt="" className="h-8 w-8 shrink-0" />
          {!collapsed && (
            <span className="font-bold text-slate-900 tracking-tight text-sm truncate">Field Worker Tracker</span>
          )}
        </Link>

        {/* Navigation */}
        <ScrollArea className="flex-1">
          <nav aria-label="Main" className={`py-3 ${collapsed ? "px-2" : "px-3"}`}>
            {groups.map((group, gi) => (
              <div key={group.label} className={gi > 0 ? "mt-3" : undefined}>
                {collapsed ? (
                  gi > 0 && <div className="mx-2 mb-3 border-t border-slate-100" aria-hidden />
                ) : (
                  <div className="px-3 pb-1 text-[10px] font-semibold uppercase tracking-wider text-slate-400">
                    {group.label}
                  </div>
                )}
                <ul className="space-y-0.5" aria-label={group.label}>
                  {group.items.map((item) => {
                    const Icon = item.icon;
                    const active = isNavItemActive(item, currentPath, currentSearch, currentHash);
                    return (
                      <li key={item.label}>
                        <Link
                          to={item.to}
                          search={item.search as never}
                          hash={item.hash}
                          title={item.label}
                          aria-current={active ? "page" : undefined}
                          className={`relative flex items-center rounded-lg transition-colors ${
                            collapsed ? "justify-center p-2.5" : "gap-3 px-3 py-1.5 text-sm font-medium"
                          } ${
                            active
                              ? "bg-indigo-50 text-indigo-700 font-semibold"
                              : "text-slate-600 hover:bg-slate-100 hover:text-slate-900"
                          }`}
                        >
                          <Icon
                            className={`${collapsed ? "h-5 w-5" : "h-4 w-4"} shrink-0 ${
                              active ? "text-indigo-600" : "text-slate-400"
                            }`}
                          />
                          {!collapsed && <span className="truncate">{item.label}</span>}
                          {item.to === "/approvals" && pendingApprovalsCount > 0 && (
                            <span
                              className={`${
                                isCollapsed
                                  ? "absolute top-1 right-1 h-2.5 w-2.5 rounded-full"
                                  : "ml-auto px-1.5 py-0.5 rounded-full text-2xs"
                              } bg-rose-500 text-white font-bold shadow-2xs`}
                            >
                              {!collapsed && pendingApprovalsCount}
                            </span>
                          )}
                        </Link>
                      </li>
                    );
                  })}
                </ul>
              </div>
            ))}
          </nav>
        </ScrollArea>

        {/* Sidebar Footer: collapse toggle and version */}
        <div
          className={`border-t border-slate-200 flex items-center ${
            collapsed ? "flex-col gap-2 p-2" : "justify-between gap-2 px-3 py-2.5"
          }`}
        >
          <button
            type="button"
            onClick={toggleSidebar}
            hidden={isNarrow}
            className="p-1.5 rounded-lg text-slate-400 hover:text-slate-700 hover:bg-slate-100 transition shrink-0"
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-label={collapsed ? "Expand sidebar" : "Collapse sidebar"}
            aria-expanded={!collapsed}
          >
            {collapsed ? <PanelLeftOpen className="h-4 w-4" /> : <PanelLeftClose className="h-4 w-4" />}
          </button>
          {collapsed ? (
            <span className="h-2.5 w-2.5 rounded-full bg-emerald-500 shadow-2xs" title={`System Active (v${APP_VERSION})`} />
          ) : (
            <span className="flex items-center gap-2 text-xs text-slate-500">
              <span className="h-2 w-2 rounded-full bg-emerald-500 inline-block" title="System Active" />
              <span
                className="px-2 py-0.5 rounded bg-slate-100 font-mono text-[10px] text-slate-700 font-bold border border-slate-200"
                title="System Version"
              >
                v{APP_VERSION}
              </span>
            </span>
          )}
        </div>
      </aside>

      {/* Main Content Area */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top Header */}
        <header className="h-16 border-b border-slate-200 bg-white flex items-center justify-between gap-3 px-4 md:px-8 shrink-0">
          <div className="flex min-w-0 items-center gap-2">
            {isNarrow && (
              <button
                type="button"
                onClick={() => setDrawerOpen(true)}
                className="-ml-1 p-2 rounded-lg text-slate-500 hover:bg-slate-100"
                aria-label="Open menu"
                aria-controls="app-sidebar"
                aria-expanded={drawerOpen}
              >
                <Menu className="h-5 w-5" />
              </button>
            )}
            <h1 className="truncate text-lg font-semibold text-slate-800">
              {title}
            </h1>
          </div>
          <div className="flex items-center gap-4">
            <div className="hidden lg:flex items-center gap-2 px-2.5 py-1 rounded-full bg-slate-100 text-slate-700 text-xs font-medium">
              <ShieldCheck className="h-3.5 w-3.5 text-slate-500" />
              <span>Deployment: <strong>AE</strong> (UAE North)</span>
            </div>

            <div className="flex items-center gap-3 lg:pl-4 lg:border-l border-slate-200">
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
        <main
          className={`flex-1 flex flex-col min-h-0 ${
            currentPath === "/live" ? "p-0 overflow-hidden" : "p-4 md:p-8 overflow-y-auto fw-scroll"
          }`}
        >
          {children}
        </main>
      </div>
    </div>
  );
};
