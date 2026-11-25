import {
  createRootRoute,
  createRoute,
  createRouter,
  lazyRouteComponent,
  Outlet,
} from "@tanstack/react-router";
import { Shell } from "./components/layout/Shell";
import { Dashboard } from "./routes/Dashboard";
import { Login } from "./routes/Login";
import { SkeletonText } from "./ui";

// Batch 9 step 3: every page except the Dashboard (the landing page) and Login is its own chunk,
// loaded on first visit and preloaded when a menu link is hovered or focused.
const LiveMap = lazyRouteComponent(() => import("./routes/LiveMap"), "LiveMap");
const BasePlanner = lazyRouteComponent(() => import("./routes/BasePlanner"), "BasePlanner");
const OperationalPlanner = lazyRouteComponent(() => import("./routes/OperationalPlanner"), "OperationalPlanner");
const Attendance = lazyRouteComponent(() => import("./routes/Attendance"), "Attendance");
const Payroll = lazyRouteComponent(() => import("./routes/Payroll"), "Payroll");
const Reports = lazyRouteComponent(() => import("./routes/Reports"), "Reports");
const Settings = lazyRouteComponent(() => import("./routes/Settings"), "Settings");
const Employees = lazyRouteComponent(() => import("./routes/Employees"), "Employees");
const EmployeeDetail = lazyRouteComponent(() => import("./routes/EmployeeDetail"), "EmployeeDetail");
const UsersAdmin = lazyRouteComponent(() => import("./routes/Users"), "UsersAdmin");
const AuditLogs = lazyRouteComponent(() => import("./routes/AuditLogs"), "AuditLogs");
const Imports = lazyRouteComponent(() => import("./routes/Imports"), "Imports");
const SalaryStructures = lazyRouteComponent(() => import("./routes/SalaryStructures"), "SalaryStructures");
const Worksites = lazyRouteComponent(() => import("./routes/Worksites"), "Worksites");
const WorksiteDetail = lazyRouteComponent(() => import("./routes/WorksiteDetail"), "WorksiteDetail");
const Boundaries = lazyRouteComponent(() => import("./routes/Boundaries"), "Boundaries");
const Approvals = lazyRouteComponent(() => import("./routes/Approvals"), "Approvals");
const LeaveManagement = lazyRouteComponent(() => import("./routes/LeaveManagement"), "LeaveManagement");
const Devices = lazyRouteComponent(() => import("./routes/Devices"), "Devices");
const PendingVisits = lazyRouteComponent(() => import("./routes/PendingVisits"), "PendingVisits");
const Documents = lazyRouteComponent(() => import("./routes/Documents"), "Documents");
const System = lazyRouteComponent(() => import("./routes/System"), "System");
// The archive tab of Reports, as its own route.
const GeneratedReports = lazyRouteComponent(() =>
  import("./routes/Reports").then((m) => ({ default: () => <m.Reports initialTab="generated" /> }))
);

const rootRoute = createRootRoute({
  component: () => (
    <Shell>
      <Outlet />
    </Shell>
  ),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  component: Dashboard,
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: Login,
});

const employeesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/employees",
  component: Employees,
});

const employeeDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/employees/$employeeId",
  component: EmployeeDetail,
});

const usersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/users",
  component: UsersAdmin,
});

const auditLogsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/audit-logs",
  component: AuditLogs,
});

const liveRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/live",
  component: LiveMap,
});

const plannerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/planner",
  component: OperationalPlanner,
});

const basePlannerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/base-planner",
  component: BasePlanner,
});

const operationalPlannerRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/operational-planner",
  component: OperationalPlanner,
});

const attendanceRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/attendance",
  component: Attendance,
});

const payrollRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/payroll",
  component: Payroll,
});

const reportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reports",
  component: Reports,
});

const generatedReportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reports/generated",
  component: GeneratedReports,
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  component: Settings,
});

const importsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/imports",
  component: Imports,
});

const salaryStructuresRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/salary-structures",
  component: SalaryStructures,
});

const worksitesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/worksites",
  component: Worksites,
});

const worksiteDetailRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/worksites/$worksiteId",
  component: WorksiteDetail,
});

const boundariesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/boundaries",
  component: Boundaries,
});

const approvalsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/approvals",
  component: Approvals,
});

const leaveRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/leave",
  component: LeaveManagement,
});

const devicesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/devices",
  component: Devices,
});

const pendingVisitsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/pending-visits",
  component: PendingVisits,
});

const documentsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/documents",
  component: Documents,
});

const systemRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/system",
  component: System,
});

// Component gallery (Batch 10 A): development builds only; production builds drop the route
// and its code.
const devRoutes = import.meta.env.DEV
  ? [
      createRoute({
        getParentRoute: () => rootRoute,
        path: "/dev/ui",
        component: lazyRouteComponent(() => import("./routes/DevUi"), "DevUi"),
      }),
    ]
  : [];

const routeTree = rootRoute.addChildren([
  ...devRoutes,
  indexRoute,
  loginRoute,
  employeesRoute,
  employeeDetailRoute,
  worksitesRoute,
  worksiteDetailRoute,
  boundariesRoute,
  approvalsRoute,
  leaveRoute,
  devicesRoute,
  pendingVisitsRoute,
  documentsRoute,
  systemRoute,
  usersRoute,
  auditLogsRoute,
  liveRoute,
  plannerRoute,
  basePlannerRoute,
  operationalPlannerRoute,
  attendanceRoute,
  payrollRoute,
  reportsRoute,
  generatedReportsRoute,
  settingsRoute,
  importsRoute,
  salaryStructuresRoute,
]);

export const router = createRouter({
  routeTree,
  // Hovering or focusing a link fetches that page's code, so the click shows it at once.
  defaultPreload: "intent",
  // Data comes from the page's own cached queries, not route loaders: nothing to preload but code.
  defaultPreloadStaleTime: 0,
  defaultPendingComponent: () => (
    <div aria-busy="true" aria-label="Loading page">
      <SkeletonText lines={6} />
    </div>
  ),
  defaultPendingMs: 150,
});

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
