/**
 * Date helpers for DatePicker, DateRangePicker and Calendar (Batch 10 A).
 *
 * Values are ISO dates ("2026-11-25"), as the API and `<input type="date">` use. All arithmetic
 * is on UTC midnights, so the browser's time zone never shifts a day. Display follows the app's
 * en-GB style ("25 Nov 2026"). Typed dates are day-first ("25/11/2026"), as in the UAE and KSA.
 */

export const MONTHS_SHORT = [
  "Jan",
  "Feb",
  "Mar",
  "Apr",
  "May",
  "Jun",
  "Jul",
  "Aug",
  "Sep",
  "Oct",
  "Nov",
  "Dec",
] as const;
export const MONTHS_LONG = [
  "January",
  "February",
  "March",
  "April",
  "May",
  "June",
  "July",
  "August",
  "September",
  "October",
  "November",
  "December",
] as const;
/** Index 0 = Monday (ISO weekday - 1). */
export const WEEKDAYS_SHORT = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"] as const;

export interface YearMonth {
  year: number;
  /** 1-12 */
  month: number;
}

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

function utc(y: number, m: number, d: number): Date {
  return new Date(Date.UTC(y, m - 1, d));
}

export function toIso(year: number, month: number, day: number): string {
  return `${String(year).padStart(4, "0")}-${pad(month)}-${pad(day)}`;
}

/** Parses "YYYY-MM-DD" and rejects impossible dates (31 Feb). */
export function parseIso(iso: string | null | undefined): { y: number; m: number; d: number } | null {
  if (!iso) return null;
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(iso.trim());
  if (!match) return null;
  const [y, m, d] = [Number(match[1]), Number(match[2]), Number(match[3])];
  const dt = utc(y, m, d);
  if (dt.getUTCFullYear() !== y || dt.getUTCMonth() !== m - 1 || dt.getUTCDate() !== d) return null;
  return { y, m, d };
}

export function isValidIso(iso: string | null | undefined): boolean {
  return parseIso(iso) !== null;
}

/** Today in the browser's own calendar (the user's local day). */
export function todayIso(now: Date = new Date()): string {
  return toIso(now.getFullYear(), now.getMonth() + 1, now.getDate());
}

export function addDays(iso: string, days: number): string {
  const p = parseIso(iso);
  if (!p) return iso;
  const dt = utc(p.y, p.m, p.d + days);
  return toIso(dt.getUTCFullYear(), dt.getUTCMonth() + 1, dt.getUTCDate());
}

export function addMonths(ym: YearMonth, months: number): YearMonth {
  const index = ym.year * 12 + (ym.month - 1) + months;
  return { year: Math.floor(index / 12), month: (index % 12) + 1 };
}

/** The same day in another month, clamped to that month's length (31 Jan + 1 -> 28/29 Feb). */
export function addMonthsToIso(iso: string, months: number): string {
  const p = parseIso(iso);
  if (!p) return iso;
  const target = addMonths({ year: p.y, month: p.m }, months);
  return toIso(target.year, target.month, Math.min(p.d, daysInMonth(target)));
}

export function daysInMonth(ym: YearMonth): number {
  return utc(ym.year, ym.month + 1, 0).getUTCDate();
}

export function monthOf(iso: string | null | undefined, fallback: YearMonth): YearMonth {
  const p = parseIso(iso);
  return p ? { year: p.y, month: p.m } : fallback;
}

/** ISO weekday index, 0 = Monday ... 6 = Sunday. */
export function weekdayIndex(iso: string): number {
  const p = parseIso(iso);
  if (!p) return 0;
  return (utc(p.y, p.m, p.d).getUTCDay() + 6) % 7;
}

export function formatDisplayDate(
  iso: string | null | undefined,
  options: { weekday?: boolean } = {},
): string {
  const p = parseIso(iso);
  if (!p) return "";
  const base = `${p.d} ${MONTHS_SHORT[p.m - 1]} ${p.y}`;
  return options.weekday ? `${WEEKDAYS_SHORT[weekdayIndex(iso as string)]}, ${base}` : base;
}

export function formatMonth(ym: YearMonth): string {
  return `${MONTHS_LONG[ym.month - 1]} ${ym.year}`;
}

export function formatRange(from: string | null | undefined, to: string | null | undefined): string {
  const a = formatDisplayDate(from);
  const b = formatDisplayDate(to);
  if (a && b) return a === b ? a : `${a} – ${b}`;
  if (a) return `From ${a}`;
  if (b) return `Until ${b}`;
  return "";
}

function monthFromName(name: string): number | null {
  const key = name.slice(0, 3).toLowerCase();
  const index = MONTHS_SHORT.findIndex((m) => m.toLowerCase() === key);
  return index >= 0 ? index + 1 : null;
}

function fullYear(y: number): number {
  return y < 100 ? 2000 + y : y;
}

/**
 * A typed date as ISO, or null. Accepts "2026-11-25", "25/11/2026", "25-11-2026",
 * "25.11.2026", "25/11/26" (day first) and "25 Nov 2026" / "25 November 2026".
 */
export function parseUserDate(input: string): string | null {
  const s = input.trim();
  if (!s) return null;
  if (isValidIso(s)) return s;
  let m = /^(\d{1,2})[/.-](\d{1,2})[/.-](\d{2}|\d{4})$/.exec(s);
  if (m) {
    const iso = toIso(fullYear(Number(m[3])), Number(m[2]), Number(m[1]));
    return isValidIso(iso) ? iso : null;
  }
  m = /^(\d{1,2})\s+([A-Za-z]{3,})\.?,?\s+(\d{2}|\d{4})$/.exec(s);
  if (m) {
    const month = monthFromName(m[2]);
    if (!month) return null;
    const iso = toIso(fullYear(Number(m[3])), month, Number(m[1]));
    return isValidIso(iso) ? iso : null;
  }
  return null;
}

export function isWithin(
  iso: string,
  min?: string | null,
  max?: string | null,
): boolean {
  if (min && iso < min) return false;
  if (max && iso > max) return false;
  return true;
}

export interface DayCell {
  iso: string;
  day: number;
  inMonth: boolean;
  /** 0 = Monday ... 6 = Sunday */
  weekday: number;
}

/** Six weeks of days covering the month, starting on `weekStartsOn` (0 = Monday). */
export function monthGrid(ym: YearMonth, weekStartsOn = 0): DayCell[][] {
  const first = toIso(ym.year, ym.month, 1);
  const lead = (weekdayIndex(first) - weekStartsOn + 7) % 7;
  let cursor = addDays(first, -lead);
  const weeks: DayCell[][] = [];
  for (let w = 0; w < 6; w += 1) {
    const week: DayCell[] = [];
    for (let i = 0; i < 7; i += 1) {
      const p = parseIso(cursor) as { y: number; m: number; d: number };
      week.push({
        iso: cursor,
        day: p.d,
        inMonth: p.m === ym.month && p.y === ym.year,
        weekday: weekdayIndex(cursor),
      });
      cursor = addDays(cursor, 1);
    }
    weeks.push(week);
  }
  return weeks;
}

/** Weekday headers in display order for `weekStartsOn`. */
export function weekdayHeaders(weekStartsOn = 0): string[] {
  return Array.from({ length: 7 }, (_, i) => WEEKDAYS_SHORT[(i + weekStartsOn) % 7]);
}

export interface DateRange {
  from: string | null;
  to: string | null;
}

/** Next range after clicking a day: first click starts, second click ends (in either order). */
export function rangeSelect(range: DateRange, iso: string): DateRange {
  if (!range.from || range.to) return { from: iso, to: null };
  return iso < range.from ? { from: iso, to: range.from } : { from: range.from, to: iso };
}

export function inRange(iso: string, range: DateRange): boolean {
  return Boolean(range.from && range.to && iso >= range.from && iso <= range.to);
}

/** Keyboard movement in a calendar grid; null for keys the grid does not handle. */
export function moveByKey(iso: string, key: string, weekStartsOn = 0): string | null {
  switch (key) {
    case "ArrowLeft":
      return addDays(iso, -1);
    case "ArrowRight":
      return addDays(iso, 1);
    case "ArrowUp":
      return addDays(iso, -7);
    case "ArrowDown":
      return addDays(iso, 7);
    case "PageUp":
      return addMonthsToIso(iso, -1);
    case "PageDown":
      return addMonthsToIso(iso, 1);
    case "Home":
      return addDays(iso, -((weekdayIndex(iso) - weekStartsOn + 7) % 7));
    case "End":
      return addDays(iso, 6 - ((weekdayIndex(iso) - weekStartsOn + 7) % 7));
    default:
      return null;
  }
}
