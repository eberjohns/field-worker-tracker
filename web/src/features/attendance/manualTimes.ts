/** Form rules for entering a day's times (ManualTimesModal). Pure, so tests need no DOM. */

/** "06:00:00" or "06:00" -> "06:00" ("" when unknown). */
export function toHhMm(value: string | null | undefined): string {
  if (!value) return "";
  const m = /^(\d{1,2}):(\d{2})/.exec(value);
  return m ? `${m[1].padStart(2, "0")}:${m[2]}` : "";
}

export interface ManualTimesForm {
  firstSiteEntry: string;
  lastSiteExit: string;
  accommodationDeparture: string;
  accommodationReturn: string;
  reason: string;
}

/** Field errors before sending (the server checks the same rules). */
export function validateManualTimes(f: ManualTimesForm): Partial<Record<keyof ManualTimesForm, string>> {
  const errors: Partial<Record<keyof ManualTimesForm, string>> = {};
  if (!f.firstSiteEntry) errors.firstSiteEntry = "Enter the first site entry.";
  if (!f.lastSiteExit) errors.lastSiteExit = "Enter the last site exit.";
  if (f.firstSiteEntry && f.lastSiteExit && f.lastSiteExit <= f.firstSiteEntry) {
    errors.lastSiteExit = "Must be after the first site entry (same day).";
  }
  if (Boolean(f.accommodationDeparture) !== Boolean(f.accommodationReturn)) {
    const msg = "Enter both accommodation times, or neither.";
    if (!f.accommodationDeparture) errors.accommodationDeparture = msg;
    else errors.accommodationReturn = msg;
  }
  if (f.accommodationDeparture && f.firstSiteEntry && f.accommodationDeparture > f.firstSiteEntry) {
    errors.accommodationDeparture = "Must be before the first site entry.";
  }
  if (f.accommodationReturn && f.lastSiteExit && f.accommodationReturn < f.lastSiteExit) {
    errors.accommodationReturn = "Must be after the last site exit.";
  }
  if (!f.reason.trim()) errors.reason = "A reason is required.";
  return errors;
}
