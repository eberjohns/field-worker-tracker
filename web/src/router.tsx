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

const routeTree = rootRoute.addChildren([
  indexRoute,
  liveRoute,
  plannerRoute,
  attendanceRoute,
  payrollRoute,
  reportsRoute,
  settingsRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}

