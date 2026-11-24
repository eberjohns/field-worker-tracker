/**
 * Overlay plumbing shared by Modal, popovers (DatePicker, DateRangePicker, Menu) and Tooltip
 * (Batch 10 A): portal, Escape, outside click, focus trap, scroll lock and anchored placement.
 * Everything checks for `document`, so components also render on the server (tests).
 */
import React, { useEffect, useLayoutEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

const hasDom = typeof window !== "undefined" && typeof document !== "undefined";

/** useLayoutEffect in the browser, useEffect on the server (no warning). */
export const useIsoLayoutEffect = hasDom ? useLayoutEffect : useEffect;

/** Renders children into document.body; inline when there is no DOM. */
export const Portal: React.FC<{ children: React.ReactNode }> = ({ children }) =>
  hasDom ? createPortal(children, document.body) : <>{children}</>;

export function useEscapeKey(onEscape: () => void, active: boolean): void {
  const handler = useRef(onEscape);
  handler.current = onEscape;
  useEffect(() => {
    if (!active || !hasDom) return;
    const listener = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        e.stopPropagation();
        handler.current();
      }
    };
    document.addEventListener("keydown", listener);
    return () => document.removeEventListener("keydown", listener);
  }, [active]);
}

/** Calls `onOutside` for a pointer press outside every given element. */
export function useOutsideClick(
  refs: ReadonlyArray<React.RefObject<HTMLElement | null>>,
  onOutside: () => void,
  active: boolean,
): void {
  const handler = useRef(onOutside);
  handler.current = onOutside;
  const refsRef = useRef(refs);
  refsRef.current = refs;
  useEffect(() => {
    if (!active || !hasDom) return;
    const listener = (e: PointerEvent) => {
      const target = e.target as Node | null;
      if (!target) return;
      if (refsRef.current.some((r) => r.current?.contains(target))) return;
      handler.current();
    };
    document.addEventListener("pointerdown", listener);
    return () => document.removeEventListener("pointerdown", listener);
  }, [active]);
}

const FOCUSABLE =
  'a[href], button:not([disabled]), input:not([disabled]):not([type="hidden"]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex="-1"])';

export function focusableIn(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => !el.hasAttribute("aria-hidden") && el.offsetParent !== null,
  );
}

/**
 * While active: focus moves into the container (or `initialFocus`), Tab cycles inside it, and on
 * close focus returns to whatever had it before.
 */
export function useFocusTrap(
  container: React.RefObject<HTMLElement | null>,
  active: boolean,
  initialFocus?: React.RefObject<HTMLElement | null>,
): void {
  useEffect(() => {
    if (!active || !hasDom) return;
    const previous = document.activeElement as HTMLElement | null;
    const node = container.current;
    const first = initialFocus?.current ?? (node ? focusableIn(node)[0] : null) ?? node;
    first?.focus({ preventScroll: true });
    const onKey = (e: KeyboardEvent) => {
      if (e.key !== "Tab" || !container.current) return;
      const items = focusableIn(container.current);
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const firstItem = items[0];
      const lastItem = items[items.length - 1];
      if (e.shiftKey && document.activeElement === firstItem) {
        e.preventDefault();
        lastItem.focus();
      } else if (!e.shiftKey && document.activeElement === lastItem) {
        e.preventDefault();
        firstItem.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      previous?.focus?.({ preventScroll: true });
    };
  }, [active, container, initialFocus]);
}

let scrollLocks = 0;

/** Stops the page behind a modal from scrolling (nested modals share one lock). */
export function useBodyScrollLock(active: boolean): void {
  useEffect(() => {
    if (!active || !hasDom) return;
    scrollLocks += 1;
    const previous = document.body.style.overflow;
    if (scrollLocks === 1) document.body.style.overflow = "hidden";
    return () => {
      scrollLocks -= 1;
      if (scrollLocks === 0) document.body.style.overflow = previous;
    };
  }, [active]);
}

export type Placement = "bottom-start" | "bottom-end" | "top" | "bottom";

export interface AnchoredPosition {
  top: number;
  left: number;
  placement: "above" | "below";
}

/**
 * Where a floating panel goes next to its anchor, in viewport coordinates. It flips above when
 * there is no room below and stays inside the viewport horizontally.
 */
export function computePosition(
  anchor: { top: number; bottom: number; left: number; right: number; width: number },
  panel: { width: number; height: number },
  viewport: { width: number; height: number },
  placement: Placement = "bottom-start",
  gap = 6,
): AnchoredPosition {
  const roomBelow = viewport.height - anchor.bottom - gap;
  const roomAbove = anchor.top - gap;
  const below = placement === "top" ? roomAbove < panel.height : roomBelow >= panel.height || roomBelow >= roomAbove;
  const top = below ? anchor.bottom + gap : anchor.top - gap - panel.height;
  let left: number;
  if (placement === "bottom-end") left = anchor.right - panel.width;
  else if (placement === "top" || placement === "bottom") left = anchor.left + anchor.width / 2 - panel.width / 2;
  else left = anchor.left;
  left = Math.max(8, Math.min(left, viewport.width - panel.width - 8));
  return { top: Math.max(8, top), left, placement: below ? "below" : "above" };
}

/** Keeps a fixed-position panel next to its anchor while open (scroll and resize included). */
export function useAnchoredPosition(
  anchor: React.RefObject<HTMLElement | null>,
  panel: React.RefObject<HTMLElement | null>,
  open: boolean,
  placement: Placement = "bottom-start",
): AnchoredPosition | null {
  const [pos, setPos] = useState<AnchoredPosition | null>(null);
  useIsoLayoutEffect(() => {
    if (!open || !hasDom) {
      setPos(null);
      return;
    }
    const update = () => {
      const a = anchor.current?.getBoundingClientRect();
      const p = panel.current?.getBoundingClientRect();
      if (!a || !p) return;
      setPos(
        computePosition(
          a,
          { width: p.width, height: p.height },
          { width: window.innerWidth, height: window.innerHeight },
          placement,
        ),
      );
    };
    update();
    window.addEventListener("resize", update);
    window.addEventListener("scroll", update, true);
    return () => {
      window.removeEventListener("resize", update);
      window.removeEventListener("scroll", update, true);
    };
  }, [open, anchor, panel, placement]);
  return pos;
}
