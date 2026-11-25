import React, { useEffect } from "react";
import { AlertTriangle, CheckCircle2, Info, X, XCircle } from "lucide-react";
import { cn } from "./cn";
import { FieldErrorList } from "./AlertBanner";
import { Portal } from "./overlay";
import type { ToastItem, ToastTone } from "./toastStore";

const tones: Record<ToastTone, { icon: React.ReactNode; accent: string }> = {
  success: { icon: <CheckCircle2 className="h-4 w-4 text-fw-success" />, accent: "border-l-fw-success" },
  info: { icon: <Info className="h-4 w-4 text-fw-info" />, accent: "border-l-fw-info" },
  warning: { icon: <AlertTriangle className="h-4 w-4 text-fw-warning" />, accent: "border-l-fw-warning" },
  error: { icon: <XCircle className="h-4 w-4 text-fw-danger" />, accent: "border-l-fw-danger" },
};

const ToastCard: React.FC<{ toast: ToastItem; onDismiss: (id: number) => void }> = ({ toast, onDismiss }) => {
  useEffect(() => {
    if (toast.durationMs === null) return;
    const timer = setTimeout(() => onDismiss(toast.id), toast.durationMs);
    return () => clearTimeout(timer);
  }, [toast.id, toast.durationMs, onDismiss]);
  return (
    <div
      role={toast.tone === "error" ? "alert" : "status"}
      className={cn(
        "fw-animate-pop pointer-events-auto flex w-80 max-w-[calc(100vw-2rem)] gap-2.5 rounded-fw-lg border border-l-4 border-fw-border bg-fw-surface px-3 py-2.5 shadow-fw-md",
        tones[toast.tone].accent,
      )}
    >
      <span className="mt-0.5 shrink-0" aria-hidden="true">
        {tones[toast.tone].icon}
      </span>
      <div className="min-w-0 flex-1 text-fw-sm">
        <p className="font-medium text-fw-text">{toast.title}</p>
        {toast.message && <p className="mt-0.5 text-fw-text-muted">{toast.message}</p>}
        {toast.fields.length > 0 && <FieldErrorList fields={toast.fields} className="mt-1 text-fw-text-muted" />}
      </div>
      <button
        type="button"
        onClick={() => onDismiss(toast.id)}
        aria-label="Dismiss notification"
        className="-mr-1 -mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-fw-sm text-fw-text-subtle hover:bg-fw-muted hover:text-fw-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus"
      >
        <X className="h-3.5 w-3.5" />
      </button>
    </div>
  );
};

/** Bottom-right stack of notifications (newest at the bottom). */
export const Toaster: React.FC<{ toasts: ToastItem[]; onDismiss: (id: number) => void }> = ({ toasts, onDismiss }) => (
  <Portal>
    <div
      aria-live="polite"
      aria-label="Notifications"
      className="pointer-events-none fixed bottom-4 right-4 z-fw-toast flex flex-col items-end gap-2"
    >
      {toasts.map((t) => (
        <ToastCard key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  </Portal>
);
