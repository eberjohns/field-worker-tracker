import {
  createRootRoute,
  createRoute,
  createRouter,
  Outlet,
} from "@tanstack/react-router";
import { Shell } from "./components/layout/Shell";
import { Dashboard } from "./routes/Dashboard";
import { LiveMap } from "./routes/LiveMap";
import { Planner } from "./routes/Planner";
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
  component: Planner,
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

const routeTree = rootRoute.addChildren([
  indexRoute,
  loginRoute,
  employeesRoute,
  employeeDetailRoute,
  usersRoute,
  auditLogsRoute,
  liveRoute,
  plannerRoute,
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
