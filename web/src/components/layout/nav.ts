/**
 * The app menu (Batch 10 B): groups in the owner's order, role filtering, page titles and the
 * active item. Kept apart from Shell.tsx so it can be tested without the app around it.
 */
import type React from "react";
import {
  LayoutDashboard,
  MapPin,
  CalendarDays,
  CalendarCheck,
  CheckSquare,
  Clock,
  DollarSign,
  FileBarChart,
  Settings as SettingsIcon,
  ShieldCheck,
  Users,
  UserCheck,
  History,
  UploadCloud,
  Banknote,
  Building2,
  Hexagon,
  CalendarRange,
  Smartphone,
  AlertTriangle,
  Server,
  UserMinus,
  Home,
  ScrollText,
} from "lucide-react";

export interface NavItem {
  label: string;
  to: string;
  icon: React.ComponentType<{ className?: string }>;
  roles?: string[];
  /** Optional search or hash, for items that open a tab or section of a page. */
  search?: Record<string, string>;
  hash?: string;
}

export interface NavGroup {
  label: string;
  items: NavItem[];
}

const LEADS = ["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"];

/** The menu (Batch 10 B): groups and items in the owner's order; a role sees only what it can use. */
export const navGroups: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", to: "/", icon: LayoutDashboard },
      { label: "Live Map", to: "/live", icon: MapPin },
    ],
  },
  {
    label: "Planning",
    items: [
      { label: "Base Planner", to: "/base-planner", icon: CalendarRange, roles: LEADS },
      { label: "Operational Planner", to: "/operational-planner", icon: CalendarDays, roles: LEADS },
      { label: "Leave", to: "/leave", icon: CalendarCheck, roles: LEADS },
      { label: "Approvals", to: "/approvals", icon: CheckSquare, roles: ["ADMIN", "ENGINEER", "SUPERINTENDENT"] },
      { label: "Staffing Gaps", to: "/operational-planner", hash: "staffing-gaps", icon: UserMinus, roles: LEADS },
    ],
  },
  {
    label: "Workforce",
    items: [
      { label: "Employees", to: "/employees", icon: Users, roles: LEADS },
      { label: "Documents", to: "/documents", icon: ShieldCheck, roles: ["ADMIN"] },
      { label: "Devices", to: "/devices", icon: Smartphone, roles: ["ADMIN", "ENGINEER", "SUPERINTENDENT"] },
    ],
  },
  {
    label: "Sites",
    items: [
      { label: "Worksites", to: "/worksites", icon: Building2, roles: LEADS },
      { label: "Boundaries", to: "/boundaries", icon: Hexagon, roles: ["ADMIN", "ENGINEER"] },
      { label: "Accommodations", to: "/worksites", search: { tab: "accommodations" }, icon: Home, roles: LEADS },
    ],
  },
  {
    label: "Time & Pay",
    items: [
      { label: "Attendance", to: "/attendance", icon: Clock },
      { label: "Pending Visits", to: "/pending-visits", icon: AlertTriangle, roles: LEADS },
      { label: "Payroll", to: "/payroll", icon: DollarSign, roles: ["ADMIN"] },
      { label: "Salary Structures", to: "/salary-structures", icon: Banknote, roles: ["ADMIN"] },
    ],
  },
  {
    label: "Reports",
    items: [
      { label: "Reports", to: "/reports", icon: FileBarChart },
      { label: "Generated Reports", to: "/reports/generated", icon: History },
    ],
  },
  {
    label: "Admin",
    items: [
      { label: "Master Data Import", to: "/imports", icon: UploadCloud, roles: ["ADMIN"] },
      { label: "Settings", to: "/settings", icon: SettingsIcon, roles: ["ADMIN", "ENGINEER"] },
      { label: "Users & Security", to: "/users", icon: UserCheck, roles: ["ADMIN"] },
      { label: "Audit Logs", to: "/audit-logs", icon: ScrollText, roles: ["ADMIN"] },
      { label: "System", to: "/system", icon: Server },
    ],
  },
];

/** Groups with only the items `role` may use; empty groups are dropped. */
export function navForRole(role: string | undefined): NavGroup[] {
  return navGroups
    .map((g) => ({ ...g, items: g.items.filter((i) => !i.roles || (role !== undefined && i.roles.includes(role))) }))
    .filter((g) => g.items.length > 0);
}

/** Pages that are not in the menu, or detail pages under a menu item. */
const EXTRA_TITLES: [RegExp, string][] = [
  [/^\/employees\/[^/]+$/, "Employee"],
  [/^\/worksites\/[^/]+$/, "Worksite"],
  [/^\/planner$/, "Planner"],
  [/^\/login$/, "Sign in"],
];

/** The page title for a path: the menu label, else a detail page name. */
export function pageTitle(path: string, search: Record<string, unknown> = {}): string {
  for (const [re, title] of EXTRA_TITLES) if (re.test(path)) return title;
  const items = navGroups.flatMap((g) => g.items).filter((i) => i.to === path && !i.hash);
  const bySearch = items.find((i) => i.search && Object.entries(i.search).every(([k, v]) => search[k] === v));
  return (bySearch ?? items.find((i) => !i.search))?.label ?? "Field Worker Tracker";
}

/** Is `item` the current page? A search/hash item wins over the plain item with the same path. */
export function isNavItemActive(
  item: NavItem,
  path: string,
  search: Record<string, unknown>,
  hash: string,
): boolean {
  const matchesExtra = (i: NavItem) =>
    (i.search !== undefined && Object.entries(i.search).every(([k, v]) => search[k] === v)) ||
    (i.hash !== undefined && hash === i.hash);
  const all = navGroups.flatMap((g) => g.items);
  if (path !== item.to) {
    // detail pages (/employees/123) highlight their list item
    return item.to !== "/" && !item.search && !item.hash && path.startsWith(`${item.to}/`) &&
      !all.some((o) => o.to.length > item.to.length && path.startsWith(o.to));
  }
  if (item.search || item.hash) return matchesExtra(item);
  return !all.some((o) => o !== item && o.to === item.to && matchesExtra(o));
}
