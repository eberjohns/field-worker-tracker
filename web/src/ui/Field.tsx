import React from "react";
import { cn } from "./cn";

export interface FieldProps {
  label?: React.ReactNode;
  /** Help text under the control. */
  hint?: React.ReactNode;
  /** Error text under the control; marks the control invalid. */
  error?: React.ReactNode;
  required?: boolean;
  /** The control's id, for the label. */
  htmlFor?: string;
  className?: string;
  children: React.ReactNode;
}

/** Label, control, then hint or error: the frame every form control uses. */
export const Field: React.FC<FieldProps> = ({ label, hint, error, required, htmlFor, className, children }) => (
  <div className={cn("flex flex-col gap-1", className)}>
    {label && (
      <label htmlFor={htmlFor} className="text-fw-xs font-medium text-fw-text-muted">
        {label}
        {required && (
          <span className="ml-0.5 text-fw-danger" aria-hidden="true">
            *
          </span>
        )}
      </label>
    )}
    {children}
    {error ? (
      <p id={htmlFor ? `${htmlFor}-error` : undefined} className="text-fw-xs text-fw-danger-text" role="alert">
        {error}
      </p>
    ) : hint ? (
      <p id={htmlFor ? `${htmlFor}-hint` : undefined} className="text-fw-xs text-fw-text-subtle">
        {hint}
      </p>
    ) : null}
  </div>
);

/** Shared look of text-like controls (input, select, the date picker's field). */
export function controlClass(opts: { invalid?: boolean; disabled?: boolean; size?: "sm" | "md" } = {}): string {
  return cn(
    "w-full rounded-fw-md border bg-fw-surface text-fw-text placeholder:text-fw-text-subtle",
    "focus:outline-none focus:ring-2 focus:ring-fw-focus/40 focus:border-fw-focus",
    opts.size === "sm" ? "h-7 px-2 text-fw-xs" : "h-8 px-2.5 text-fw-sm",
    opts.invalid ? "border-fw-danger" : "border-fw-border-strong",
    opts.disabled && "cursor-not-allowed bg-fw-muted text-fw-text-muted",
  );
}

/** aria-describedby for a control with a hint or error under it. */
export function describedBy(id: string | undefined, hint: unknown, error: unknown): string | undefined {
  if (!id) return undefined;
  if (error) return `${id}-error`;
  if (hint) return `${id}-hint`;
  return undefined;
}
