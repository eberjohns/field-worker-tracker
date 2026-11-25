import React, { useEffect, useId, useRef, useState } from "react";
import { CalendarDays, X } from "lucide-react";
import { Calendar, type CalendarProps } from "./Calendar";
import { cn } from "./cn";
import { formatDisplayDate, isWithin, parseUserDate } from "./dates";
import { controlClass, describedBy, Field } from "./Field";
import { Popover } from "./Popover";

export interface DatePickerProps {
  /** ISO date ("2026-11-25"), or "" for none: the same value `<input type="date">` uses. */
  value: string;
  onChange: (iso: string) => void;
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  min?: string | null;
  max?: string | null;
  isDateDisabled?: (iso: string) => boolean;
  markers?: CalendarProps["markers"];
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  /** Show a clear (x) button when there is a value. Default: when not required. */
  clearable?: boolean;
  /** sm: filter bars; md: the ui layer's forms; lg (36px): forms whose other inputs are 36-40px. */
  size?: "sm" | "md" | "lg";
  id?: string;
  name?: string;
  className?: string;
  fieldClassName?: string;
  "aria-label"?: string;
}

/** Why typed text is not accepted, or null when it is fine. */
export function dateInputError(
  text: string,
  opts: { min?: string | null; max?: string | null; required?: boolean },
): string | null {
  if (!text.trim()) return opts.required ? "Enter a date" : null;
  const iso = parseUserDate(text);
  if (!iso) return "Use a date like 25/11/2026";
  if (!isWithin(iso, opts.min, opts.max)) {
    if (opts.min && iso < opts.min) return `On or after ${formatDisplayDate(opts.min)}`;
    return `On or before ${formatDisplayDate(opts.max)}`;
  }
  return null;
}

/**
 * The app's only date input: type a date (25/11/2026, 25 Nov 2026 or ISO) or pick it from the
 * calendar. Shows "25 Nov 2026"; reports ISO, like a native date input.
 */
export const DatePicker: React.FC<DatePickerProps> = ({
  value,
  onChange,
  label,
  hint,
  error,
  min,
  max,
  isDateDisabled,
  markers,
  placeholder = "dd/mm/yyyy",
  required,
  disabled,
  clearable,
  size = "md",
  id,
  name,
  className,
  fieldClassName,
  "aria-label": ariaLabel,
}) => {
  const auto = useId();
  const inputId = id ?? auto;
  const popoverId = `${inputId}-calendar`;
  const anchorRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const [open, setOpen] = useState(false);
  const [text, setText] = useState(() => formatDisplayDate(value));
  const [typingError, setTypingError] = useState<string | null>(null);

  useEffect(() => {
    setText(formatDisplayDate(value));
    setTypingError(null);
  }, [value]);

  const commit = (raw: string) => {
    const problem = dateInputError(raw, { min, max, required: false });
    if (problem) {
      setTypingError(problem);
      return;
    }
    const iso = raw.trim() ? (parseUserDate(raw) as string) : "";
    if (iso && isDateDisabled?.(iso)) {
      setTypingError("That date cannot be chosen");
      return;
    }
    setTypingError(null);
    setText(formatDisplayDate(iso));
    if (iso !== value) onChange(iso);
  };

  const pick = (iso: string) => {
    setOpen(false);
    setTypingError(null);
    setText(formatDisplayDate(iso));
    if (iso !== value) onChange(iso);
    inputRef.current?.focus();
  };

  const showClear = (clearable ?? !required) && Boolean(value) && !disabled;
  const shownError = error ?? typingError;
  return (
    <Field label={label} hint={hint} error={shownError} required={required} htmlFor={inputId} className={fieldClassName}>
      <div ref={anchorRef} className="relative flex items-center">
        <input
          ref={inputRef}
          id={inputId}
          name={name}
          type="text"
          inputMode="numeric"
          autoComplete="off"
          value={text}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          aria-label={ariaLabel}
          aria-invalid={shownError ? true : undefined}
          aria-describedby={describedBy(inputId, hint, shownError)}
          aria-haspopup="dialog"
          aria-expanded={open}
          aria-controls={open ? popoverId : undefined}
          onClick={() => !disabled && setOpen(true)}
          onChange={(e) => {
            setText(e.target.value);
            if (typingError) setTypingError(null);
          }}
          onBlur={() => commit(text)}
          onKeyDown={(e) => {
            if (e.key === "Enter") {
              e.preventDefault();
              commit(text);
            } else if (e.key === "ArrowDown" && e.altKey) {
              e.preventDefault();
              setOpen(true);
            }
          }}
          className={cn(controlClass({ invalid: Boolean(shownError), disabled, size }), "pr-14 tabular-nums", className)}
        />
        <div className="absolute right-1 flex items-center">
          {showClear && (
            <button
              type="button"
              tabIndex={-1}
              aria-label="Clear date"
              onClick={() => pick("")}
              className="flex h-6 w-6 items-center justify-center rounded-fw-sm text-fw-text-subtle hover:bg-fw-muted hover:text-fw-text"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
          <button
            type="button"
            disabled={disabled}
            aria-label="Choose date"
            onClick={() => setOpen((o) => !o)}
            className="flex h-6 w-6 items-center justify-center rounded-fw-sm text-fw-text-subtle hover:bg-fw-muted hover:text-fw-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus disabled:opacity-40"
          >
            <CalendarDays className="h-4 w-4" />
          </button>
        </div>
      </div>
      <Popover
        open={open}
        onClose={() => setOpen(false)}
        anchorRef={anchorRef as React.RefObject<HTMLElement>}
        id={popoverId}
        aria-label="Choose date"
      >
        <Calendar
          value={value || null}
          onSelect={pick}
          min={min}
          max={max}
          isDateDisabled={isDateDisabled}
          markers={markers}
          autoFocus
        />
      </Popover>
    </Field>
  );
};
