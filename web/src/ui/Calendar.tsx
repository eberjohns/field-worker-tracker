import React, { useEffect, useRef, useState } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "./cn";
import {
  addMonths,
  formatDisplayDate,
  formatMonth,
  inRange,
  isWithin,
  monthGrid,
  monthOf,
  moveByKey,
  todayIso,
  weekdayHeaders,
  type DateRange,
  type YearMonth,
} from "./dates";

export type DayTone = "holiday" | "off" | "leave" | "marked";

export interface CalendarProps {
  /** Selected day (single mode). */
  value?: string | null;
  /** Selected range (range mode); the days between are highlighted. */
  range?: DateRange;
  onSelect: (iso: string) => void;
  min?: string | null;
  max?: string | null;
  /** Days that cannot be picked (besides min/max). */
  isDateDisabled?: (iso: string) => boolean;
  /** Small marks on days, e.g. public holidays; the title is the day's tooltip. */
  markers?: Readonly<Record<string, { tone: DayTone; title?: string }>>;
  /** 0 = Monday (default) ... 6 = Sunday. */
  weekStartsOn?: number;
  /** The month shown first (default: the value's month, else today's). */
  initialMonth?: YearMonth;
  /** For tests and the gallery; default the browser's today. */
  today?: string;
  /** Moves focus into the grid when it appears (popovers). */
  autoFocus?: boolean;
  className?: string;
}

const markerDot: Record<DayTone, string> = {
  holiday: "bg-fw-danger",
  off: "bg-fw-text-subtle",
  leave: "bg-fw-warning",
  marked: "bg-fw-primary",
};

/** A month grid with keyboard navigation (arrows, Page Up/Down, Home/End, Enter). */
export const Calendar: React.FC<CalendarProps> = ({
  value,
  range,
  onSelect,
  min,
  max,
  isDateDisabled,
  markers,
  weekStartsOn = 0,
  initialMonth,
  today,
  autoFocus,
  className,
}) => {
  const todayValue = today ?? todayIso();
  const anchor = value ?? range?.from ?? null;
  const [month, setMonth] = useState<YearMonth>(
    () => initialMonth ?? monthOf(anchor, monthOf(todayValue, { year: 2026, month: 1 })),
  );
  const [focused, setFocused] = useState<string>(() => anchor ?? todayValue);
  const gridRef = useRef<HTMLTableElement>(null);
  const moved = useRef(false);
  const mounted = useRef(false);

  // Focus follows the keyboard, and enters the grid on first show when autoFocus is set; the
  // month buttons keep their own focus.
  useEffect(() => {
    const first = !mounted.current;
    mounted.current = true;
    if (first ? !autoFocus : !moved.current) return;
    moved.current = false;
    gridRef.current?.querySelector<HTMLButtonElement>(`button[data-iso="${focused}"]`)?.focus();
  }, [focused, month, autoFocus]);

  const disabled = (iso: string) => !isWithin(iso, min, max) || Boolean(isDateDisabled?.(iso));
  const weeks = monthGrid(month, weekStartsOn);

  const onKeyDown = (e: React.KeyboardEvent) => {
    const next = moveByKey(focused, e.key, weekStartsOn);
    if (!next) return;
    e.preventDefault();
    moved.current = true;
    setFocused(next);
    const nextMonth = monthOf(next, month);
    if (nextMonth.year !== month.year || nextMonth.month !== month.month) setMonth(nextMonth);
  };

  const shift = (n: number) => setMonth((m) => addMonths(m, n));
  const label = formatMonth(month);

  return (
    <div className={cn("w-[17rem] select-none text-fw-sm", className)}>
      <div className="mb-1 flex items-center justify-between">
        <button
          type="button"
          onClick={() => shift(-1)}
          aria-label="Previous month"
          className="flex h-7 w-7 items-center justify-center rounded-fw-md text-fw-text-muted hover:bg-fw-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <span className="font-medium text-fw-text" aria-live="polite">
          {label}
        </span>
        <button
          type="button"
          onClick={() => shift(1)}
          aria-label="Next month"
          className="flex h-7 w-7 items-center justify-center rounded-fw-md text-fw-text-muted hover:bg-fw-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>
      <table ref={gridRef} role="grid" aria-label={label} className="w-full border-collapse" onKeyDown={onKeyDown}>
        <thead>
          <tr>
            {weekdayHeaders(weekStartsOn).map((d) => (
              <th key={d} scope="col" abbr={d} className="h-7 text-center text-[11px] font-medium text-fw-text-subtle">
                {d.slice(0, 2)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {weeks.map((week) => (
            <tr key={week[0].iso}>
              {week.map((cell) => {
                const isDisabled = disabled(cell.iso);
                const selected =
                  cell.iso === value || (range && (cell.iso === range.from || cell.iso === range.to));
                const between = range ? inRange(cell.iso, range) && !selected : false;
                const marker = markers?.[cell.iso];
                const isToday = cell.iso === todayValue;
                return (
                  <td key={cell.iso} className="p-0 text-center" role="gridcell" aria-selected={selected || undefined}>
                    <button
                      type="button"
                      data-iso={cell.iso}
                      tabIndex={cell.iso === focused ? 0 : -1}
                      disabled={isDisabled}
                      aria-label={formatDisplayDate(cell.iso, { weekday: true }) + (marker?.title ? `, ${marker.title}` : "")}
                      aria-current={isToday ? "date" : undefined}
                      title={marker?.title}
                      onClick={() => {
                        setFocused(cell.iso);
                        onSelect(cell.iso);
                      }}
                      className={cn(
                        "relative mx-auto my-px flex h-8 w-8 items-center justify-center rounded-fw-md text-fw-sm tabular-nums",
                        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus",
                        cell.inMonth ? "text-fw-text" : "text-fw-text-subtle",
                        !selected && !isDisabled && "hover:bg-fw-muted",
                        between && "rounded-none bg-fw-primary-soft text-fw-primary-text",
                        selected && "bg-fw-primary font-semibold text-white",
                        isToday && !selected && "font-semibold text-fw-primary-text ring-1 ring-inset ring-fw-primary/30",
                        isDisabled && "cursor-not-allowed opacity-35 line-through",
                      )}
                    >
                      {cell.day}
                      {marker && (
                        <span
                          className={cn("absolute bottom-1 left-1/2 h-1 w-1 -translate-x-1/2 rounded-full", markerDot[marker.tone])}
                          aria-hidden="true"
                        />
                      )}
                    </button>
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
