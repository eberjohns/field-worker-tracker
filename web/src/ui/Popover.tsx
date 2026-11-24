import React, { useRef } from "react";
import { cn } from "./cn";
import { Portal, useAnchoredPosition, useEscapeKey, useOutsideClick, type Placement } from "./overlay";

export interface PopoverProps {
  open: boolean;
  onClose: () => void;
  /** The element the panel sits next to. */
  anchorRef: React.RefObject<HTMLElement>;
  placement?: Placement;
  children: React.ReactNode;
  className?: string;
  role?: string;
  "aria-label"?: string;
  id?: string;
}

/**
 * A floating panel next to its anchor (date pickers, menus). It is rendered on document.body
 * with fixed positioning, so a scrolling container or a modal never clips it.
 */
export const Popover: React.FC<PopoverProps> = ({
  open,
  onClose,
  anchorRef,
  placement = "bottom-start",
  children,
  className,
  role = "dialog",
  "aria-label": ariaLabel,
  id,
}) => {
  const panelRef = useRef<HTMLDivElement>(null);
  const pos = useAnchoredPosition(anchorRef, panelRef, open, placement);
  useEscapeKey(onClose, open);
  useOutsideClick([anchorRef, panelRef], onClose, open);
  if (!open) return null;
  return (
    <Portal>
      <div
        ref={panelRef}
        id={id}
        role={role}
        aria-label={ariaLabel}
        // Until measured it is transparent, not hidden: content inside can already take focus.
        style={pos ? { position: "fixed", top: pos.top, left: pos.left } : { position: "fixed", top: 0, left: 0, opacity: 0 }}
        className={cn(
          "fw-animate-pop z-fw-popover rounded-fw-lg border border-fw-border bg-fw-surface p-2 shadow-fw-md",
          className,
        )}
      >
        {children}
      </div>
    </Portal>
  );
};
