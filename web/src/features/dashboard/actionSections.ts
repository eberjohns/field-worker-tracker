/**
 * Dashboard "Pending actions & alerts" (Batch 10 B): one section per type, each with a count,
 * the 5 most recent items and "View all". A role sees only the sections whose page it can use
 * (the same roles as the menu in Shell.tsx).
 */

export type ActionSectionKey =
  | "docExpiry"
  | "cover"
  | "leave"
  | "reassignment"
  | "attendance"
  | "pendingVisits"
  | "boundary"
  | "unassigned"
  | "device";

const LEADS = ["ADMIN", "ENGINEER", "SUPERINTENDENT", "SUPERVISOR"];
const APPROVERS = ["ADMIN", "ENGINEER", "SUPERINTENDENT"];

/** Sections in the owner's order, with the roles that may see each. */
export const ACTION_SECTIONS: { key: ActionSectionKey; roles: string[] }[] = [
  { key: "docExpiry", roles: ["ADMIN"] },
  { key: "cover", roles: LEADS },
  { key: "leave", roles: APPROVERS },
  { key: "reassignment", roles: APPROVERS },
  { key: "attendance", roles: APPROVERS },
  { key: "pendingVisits", roles: LEADS },
  { key: "boundary", roles: ["ADMIN", "ENGINEER"] },
  { key: "unassigned", roles: ["ADMIN"] },
  { key: "device", roles: APPROVERS },
];

export function sectionsForRole(role: string | undefined): ActionSectionKey[] {
  if (!role) return [];
  return ACTION_SECTIONS.filter((s) => s.roles.includes(role)).map((s) => s.key);
}

/** Alert types shown under "Device / tracking alerts". */
export const DEVICE_ALERT_TYPES = new Set([
  "TRACKING_INTERRUPTED",
  "STALE_DEVICE",
  "NO_ACTIVITY",
  "CONSENT_WITHDRAWN",
  "DEVICE_MISMATCH_ATTEMPT",
]);

export const PREVIEW_SIZE = 5;

/** Newest first by `created_at`, at most PREVIEW_SIZE. */
export function newest<T extends { created_at?: string | null }>(items: T[], n = PREVIEW_SIZE): T[] {
  return [...items]
    .sort((a, b) => new Date(b.created_at ?? 0).getTime() - new Date(a.created_at ?? 0).getTime())
    .slice(0, n);
}
