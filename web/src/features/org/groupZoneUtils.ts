// Groups and zones chosen in worksite forms, with "Other – add new…" (DEC-60 amendment, owner
// decision 23 Nov 2026). Pure helpers, tested with node:test.

export type UnitKind = "group" | "zone";

export interface OrgUnit {
  id: string;
  code: string;
  name: string;
  is_active?: boolean;
}

/** Same rule as the server: case- and space-insensitive. */
function valueKey(v: string): string {
  return (v || "").replace(/\s+/g, "").toLowerCase();
}

/** Value of the "Other – add new…" option. */
export const NEW_UNIT = "__NEW__";

export const UNIT_LABELS: Record<UnitKind, string> = { group: "Customer Group", zone: "Zone" };

/** Admin and Engineer can add groups and zones. */
export function canAddUnit(role: string | null | undefined): boolean {
  return role === "ADMIN" || role === "ENGINEER";
}

export function unitLabel(u: OrgUnit): string {
  return u.code ? `${u.name} (${u.code})` : u.name;
}

/** Active groups or zones by name, plus the record's current one even if deactivated. */
export function unitOptions(
  items: readonly OrgUnit[],
  currentId?: string | null,
): { value: string; label: string }[] {
  return items
    .filter((u) => u.is_active !== false || u.id === currentId)
    .slice()
    .sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()))
    .map((u) => ({ value: u.id, label: unitLabel(u) }));
}

/** The existing group or zone with this name, ignoring case and spaces. */
export function findUnitByName(items: readonly OrgUnit[], name: string): OrgUnit | undefined {
  const key = valueKey(name);
  return items.find((u) => valueKey(u.name) === key);
}

/** POST body: a group needs only its name (the 3-digit code is generated); a zone needs both. */
export function unitPayload(
  kind: UnitKind,
  name: string,
  code: string,
  confirmNearMatch: boolean,
): Record<string, unknown> {
  const body: Record<string, unknown> = { name: name.trim(), confirm_near_match: confirmNearMatch };
  if (kind === "zone") body.code = code.trim();
  return body;
}
