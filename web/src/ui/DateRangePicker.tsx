import React, { useId, useRef, useState } from "react";
import { CalendarRange, X } from "lucide-react";
import { Button } from "./Button";
import { Calendar } from "./Calendar";
import { cn } from "./cn";
import { formatRange, rangeSelect, type DateRange } from "./dates";
import { controlClass, Field } from "./Field";
import { Popover } from "./Popover";

export interface DateRangeValue {
  /** ISO date or "" */
  from: string;
  /** ISO date or "" */
  to: string;
}

export interface DateRangePreset {
  label: string;
  from: string;
  to: string;
}

export interface DateRangePickerProps {
  value: DateRangeValue;
  /** Called once both ends are chosen (or with both "" when cleared). */
  onChange: (value: DateRangeValue) => void;
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  min?: string | null;
  max?: string | null;
  /** Shortcuts shown beside the calendar ("This month", "Last 7 days"). */
  presets?: readonly DateRangePreset[];
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  clearable?: boolean;
  size?: "sm" | "md";
  id?: string;
  className?: string;
  fieldClassName?: string;
}

/** A from-to period in one control: click the first day, then the last. */
export const DateRangePicker: React.FC<DateRangePickerProps> = ({
  value,
  onChange,
  label,
  hint,
  error,
  min,
  max,
  presets,
  placeholder = "Choose dates",
  required,
  disabled,
  clearable,
  size = "md",
  id,
  className,
  fieldClassName,
}) => {
  const auto = useId();
  const buttonId = id ?? auto;
  const anchorRef = useRef<HTMLButtonElement>(null);
  const [open, setOpen] = useState(false);
  const [draft, setDraft] = useState<DateRange>({ from: null, to: null });

  const start = () => {
    setDraft({ from: value.from || null, to: value.to || null });
    setOpen(true);
  };
  const choose = (iso: string) => {
    const next = rangeSelect(draft, iso);
    setDraft(next);
    if (next.from && next.to) {
      onChange({ from: next.from, to: next.to });
      setOpen(false);
      anchorRef.current?.focus();
    }
  };
  const text = formatRange(value.from, value.to);
  const showClear = (clearable ?? !required) && Boolean(value.from || value.to) && !disabled;

  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={buttonId} className={fieldClassName}>
      <div className="relative flex items-center">
        <button
          ref={anchorRef}
          id={buttonId}
          type="button"
          disabled={disabled}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-invalid={error ? true : undefined}
          onClick={() => (open ? setOpen(false) : start())}
          className={cn(
            controlClass({ invalid: Boolean(error), disabled, size }),
            "flex items-center gap-2 pr-8 text-left tabular-nums",
            !text && "text-fw-text-subtle",
            className,
          )}
        >
          <CalendarRange className="h-4 w-4 shrink-0 text-fw-text-subtle" aria-hidden="true" />
          <span className="truncate">{text || placeholder}</span>
        </button>
        {showClear && (
          <button
            type="button"
            aria-label="Clear dates"
            onClick={() => onChange({ from: "", to: "" })}
            className="absolute right-1.5 flex h-6 w-6 items-center justify-center rounded-fw-sm text-fw-text-subtle hover:bg-fw-muted hover:text-fw-text"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={anchorRef as React.RefObject<HTMLElement>}
        aria-label="Choose dates"
      >
        <div className="flex gap-3">
          {presets && presets.length > 0 && (
            <ul className="flex w-32 flex-col gap-0.5 border-r border-fw-border pr-2">
              {presets.map((p) => (
                <li key={p.label}>
                  <button
                    type="button"
                    onClick={() => {
                      onChange({ from: p.from, to: p.to });
                      setOpen(false);
                    }}
                    className="w-full rounded-fw-md px-2 py-1 text-left text-fw-sm text-fw-text-muted hover:bg-fw-muted hover:text-fw-text"
                  >
                    {p.label}
                  </button>
                </li>
              ))}
            </ul>
          )}
          <div className="flex flex-col gap-2">
            <Calendar range={draft} onSelect={choose} min={min} max={max} autoFocus />
            <div className="flex items-center justify-between border-t border-fw-border pt-2 text-fw-xs text-fw-text-muted">
              <span>{draft.from && !draft.to ? "Now pick the last day" : formatRange(draft.from, draft.to) || "Pick the first day"}</span>
              <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      </Popover>
    </Field>
  );
};
