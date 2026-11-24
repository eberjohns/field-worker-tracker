/** Roving-focus helpers for Tabs and Menu (Batch 10 A). */

export interface Disableable {
  disabled?: boolean;
}

/**
 * The index to move to for a navigation key, skipping disabled entries and wrapping around.
 * `orientation` decides which arrows apply. Returns null for keys that are not navigation.
 */
export function nextEnabledIndex(
  items: readonly Disableable[],
  current: number,
  key: string,
  orientation: "horizontal" | "vertical" = "horizontal",
): number | null {
  const enabled = items.map((item, i) => (item.disabled ? -1 : i)).filter((i) => i >= 0);
  if (enabled.length === 0) return null;
  const prevKey = orientation === "horizontal" ? "ArrowLeft" : "ArrowUp";
  const nextKey = orientation === "horizontal" ? "ArrowRight" : "ArrowDown";
  if (key === "Home") return enabled[0];
  if (key === "End") return enabled[enabled.length - 1];
  if (key !== prevKey && key !== nextKey) return null;
  const step = key === nextKey ? 1 : -1;
  const n = items.length;
  for (let k = 1; k <= n; k += 1) {
    const i = (((current + step * k) % n) + n) % n;
    if (!items[i]?.disabled) return i;
  }
  return null;
}
