import React, { useId, useRef } from "react";
import { X } from "lucide-react";
import { cn } from "./cn";
import { Portal, useBodyScrollLock, useEscapeKey, useFocusTrap } from "./overlay";
import { ScrollArea } from "./ScrollArea";

export type ModalSize = "sm" | "md" | "lg" | "xl";

export interface ModalProps {
  open: boolean;
  onClose: () => void;
  title: React.ReactNode;
  description?: React.ReactNode;
  size?: ModalSize;
  children?: React.ReactNode;
  /** Buttons at the bottom, right-aligned (primary action last). */
  footer?: React.ReactNode;
  /** False: Escape and the backdrop do not close it (e.g. while saving). Default true. */
  dismissible?: boolean;
  /** The element to focus first (default: the first field or button). */
  initialFocusRef?: React.RefObject<HTMLElement>;
  className?: string;
}

const widths: Record<ModalSize, string> = {
  sm: "max-w-sm",
  md: "max-w-lg",
  lg: "max-w-2xl",
  xl: "max-w-4xl",
};

/**
 * The one dialog frame: title, scrolling body, footer. Focus stays inside while open and
 * returns to the button that opened it; Escape and the backdrop close it unless `dismissible`
 * is false. Only the body scrolls.
 */
export const Modal: React.FC<ModalProps> = ({
  open,
  onClose,
  title,
  description,
  size = "md",
  children,
  footer,
  dismissible = true,
  initialFocusRef,
  className,
}) => {
  const titleId = useId();
  const descId = useId();
  const panelRef = useRef<HTMLDivElement>(null);
  useEscapeKey(() => dismissible && onClose(), open);
  useFocusTrap(panelRef, open, initialFocusRef);
  useBodyScrollLock(open);
  if (!open) return null;
  return (
    <Portal>
      <div className="fixed inset-0 z-fw-modal flex items-center justify-center p-4">
        <div
          className="fw-animate-fade absolute inset-0 bg-fw-overlay/40"
          aria-hidden="true"
          onClick={() => dismissible && onClose()}
        />
        <div
          ref={panelRef}
          role="dialog"
          aria-modal="true"
          aria-labelledby={titleId}
          aria-describedby={description ? descId : undefined}
          tabIndex={-1}
          className={cn(
            "fw-animate-pop relative flex max-h-[min(85vh,900px)] w-full flex-col rounded-fw-xl border border-fw-border bg-fw-surface shadow-fw-lg focus:outline-none",
            widths[size],
            className,
          )}
        >
          <div className="flex items-start justify-between gap-3 border-b border-fw-border px-4 py-3">
            <div className="min-w-0">
              <h2 id={titleId} className="text-fw-lg font-semibold text-fw-text">
                {title}
              </h2>
              {description && (
                <p id={descId} className="mt-0.5 text-fw-sm text-fw-text-muted">
                  {description}
                </p>
              )}
            </div>
            {dismissible && (
              <button
                type="button"
                onClick={onClose}
                aria-label="Close"
                className="-mr-1 flex h-7 w-7 shrink-0 items-center justify-center rounded-fw-md text-fw-text-subtle hover:bg-fw-muted hover:text-fw-text focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
          <ScrollArea className="flex-1 px-4 py-3 text-fw-base text-fw-text">{children}</ScrollArea>
          {footer && (
            <div className="flex flex-wrap items-center justify-end gap-2 border-t border-fw-border bg-fw-bg/60 px-4 py-2.5">
              {footer}
            </div>
          )}
        </div>
      </div>
    </Portal>
  );
};
