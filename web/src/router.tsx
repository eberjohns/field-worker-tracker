import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { Shell } from "./components/layout/Shell";
import { Dashboard } from "./routes/Dashboard";
import { LiveMap } from "./routes/LiveMap";
import { BasePlanner } from "./routes/BasePlanner";
import { OperationalPlanner } from "./routes/OperationalPlanner";
import { Attendance } from "./routes/Attendance";
import { Payroll } from "./routes/Payroll";
import { Reports } from "./routes/Reports";
import { Settings } from "./routes/Settings";
import { Employees } from "./routes/Employees";
import { EmployeeDetail } from "./routes/EmployeeDetail";
import { UsersAdmin } from "./routes/Users";
import { AuditLogs } from "./routes/AuditLogs";
import { Login } from "./routes/Login";
import { Imports } from "./routes/Imports";
import { SalaryStructures } from "./routes/SalaryStructures";
import { Worksites } from "./routes/Worksites";
import { WorksiteDetail } from "./routes/WorksiteDetail";
import { Boundaries } from "./routes/Boundaries";
import { Approvals } from "./routes/Approvals";
import { LeaveManagement } from "./routes/LeaveManagement";

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

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  employeesRoute,
  employeeDetailRoute,
  worksitesRoute,
  worksiteDetailRoute,
  boundariesRoute,
  approvalsRoute,
  leaveRoute,
  usersRoute,
  auditLogsRoute,
  liveRoute,
  plannerRoute,
  basePlannerRoute,
  operationalPlannerRoute,
  attendanceRoute,
  payrollRoute,
  reportsRoute,
  settingsRoute,
  importsRoute,
  salaryStructuresRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
