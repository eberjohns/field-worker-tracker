import React, { useEffect, useId, useRef, useState } from "react";
import { cn } from "./cn";
import { Portal, useAnchoredPosition, useEscapeKey } from "./overlay";

export interface TooltipProps {
  /** Short text; tooltips are hints, never the only place information lives. */
  content: React.ReactNode;
  children: React.ReactNode;
  side?: "top" | "bottom";
  /** Milliseconds before showing on hover. */
  delay?: number;
  className?: string;
}

/** A hint on hover or keyboard focus. Escape hides it. */
export const Tooltip: React.FC<TooltipProps> = ({ content, children, side = "top", delay = 300, className }) => {
  const id = useId();
  const anchorRef = useRef<HTMLSpanElement>(null);
  const tipRef = useRef<HTMLDivElement>(null);
  const timer = useRef<ReturnType<typeof setTimeout> | null>(null);
  const [open, setOpen] = useState(false);
  const pos = useAnchoredPosition(anchorRef, tipRef, open, side === "top" ? "top" : "bottom");
  useEscapeKey(() => setOpen(false), open);
  useEffect(() => () => {
    if (timer.current) clearTimeout(timer.current);
  }, []);

  const show = (wait: number) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(() => setOpen(true), wait);
  };
  const hide = () => {
    if (timer.current) clearTimeout(timer.current);
    setOpen(false);
  };

  return (
    <span
      ref={anchorRef}
      className="inline-flex"
      aria-describedby={open ? id : undefined}
      onMouseEnter={() => show(delay)}
      onMouseLeave={hide}
      onFocus={() => show(0)}
      onBlur={hide}
    >
      {children}
      {open && (
        <Portal>
          <div
            ref={tipRef}
            id={id}
            role="tooltip"
            style={pos ? { position: "fixed", top: pos.top, left: pos.left } : { position: "fixed", top: 0, left: 0, visibility: "hidden" }}
            className={cn(
              "fw-animate-fade pointer-events-none z-fw-tooltip max-w-xs rounded-fw-md bg-fw-text px-2 py-1 text-fw-xs text-white shadow-fw-md",
              className,
            )}
          >
            {content}
          </div>
        </Portal>
      )}
    </span>
  );
};
