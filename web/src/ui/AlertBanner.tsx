import React from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "./cn";
import type { FieldError } from "./errors";

export type AlertTone = "info" | "success" | "warning" | "error";

export interface AlertBannerProps {
  tone?: AlertTone;
  title?: React.ReactNode;
  children?: React.ReactNode;
  /** Per-field problems from a 422, listed under the message. */
  fields?: readonly FieldError[];
  /** A button or link (e.g. "Retry"). */
  action?: React.ReactNode;
  onDismiss?: () => void;
  className?: string;
}

const tones: Record<AlertTone, { box: string; icon: React.ReactNode }> = {
  info: { box: "border-fw-info/25 bg-fw-info-soft text-fw-info-text", icon: <Info className="h-4 w-4" /> },
  success: {
    box: "border-fw-success/25 bg-fw-success-soft text-fw-success-text",
    icon: <CheckCircle2 className="h-4 w-4" />,
  },
  warning: {
    box: "border-fw-warning/30 bg-fw-warning-soft text-fw-warning-text",
    icon: <AlertTriangle className="h-4 w-4" />,
  },
  error: { box: "border-fw-danger/25 bg-fw-danger-soft text-fw-danger-text", icon: <XCircle className="h-4 w-4" /> },
};

/** A message inside the page (not a popup): errors, warnings, notes. */
export const AlertBanner: React.FC<AlertBannerProps> = ({
  tone = "info",
  title,
  children,
  fields,
  action,
  onDismiss,
  className,
}) => (
  <div
    role={tone === "error" || tone === "warning" ? "alert" : "status"}
    className={cn("flex gap-2.5 rounded-fw-lg border px-3 py-2.5 text-fw-sm", tones[tone].box, className)}
  >
    <span className="mt-0.5 shrink-0" aria-hidden="true">
      {tones[tone].icon}
    </span>
    <div className="min-w-0 flex-1">
      {title && <p className="font-medium">{title}</p>}
      {children && <div className={cn(title && "mt-0.5", "opacity-90")}>{children}</div>}
      {fields && fields.length > 0 && <FieldErrorList fields={fields} className="mt-1" />}
      {action && <div className="mt-2">{action}</div>}
    </div>
    {onDismiss && (
      <button
        type="button"
        onClick={onDismiss}
        aria-label="Dismiss"
        className="-mr-1 -mt-0.5 h-6 w-6 shrink-0 rounded-fw-sm opacity-70 hover:opacity-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus"
      >
        <X className="mx-auto h-3.5 w-3.5" />
      </button>
    )}
  </div>
);

/** "Date from: must be before Date to", one per line. */
export const FieldErrorList: React.FC<{ fields: readonly FieldError[]; className?: string }> = ({ fields, className }) => (
  <ul className={cn("list-disc space-y-0.5 pl-4 text-fw-xs", className)}>
    {fields.map((f, i) => (
      <li key={`${f.field}-${i}`}>
        <span className="font-medium">{f.field}:</span> {f.reason}
      </li>
    ))}
  </ul>
);
