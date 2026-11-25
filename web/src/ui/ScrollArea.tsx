import React from "react";
import { cn } from "./cn";

export interface ScrollAreaProps extends React.HTMLAttributes<HTMLDivElement> {
  /** Which direction scrolls. Default: vertical. */
  axis?: "y" | "x" | "both";
  /** Cap the height (CSS length or px) instead of filling the parent. */
  maxHeight?: number | string;
}

const overflow = { y: "overflow-y-auto overflow-x-hidden", x: "overflow-x-auto overflow-y-hidden", both: "overflow-auto" };

/**
 * The one scrolling container: a thin scrollbar that appears on hover or keyboard focus
 * (`.fw-scroll` in tokens.css). Give it the height; nest it only when the inner list really
 * needs its own scroll (one scroll per region avoids "double scrolling").
 */
export const ScrollArea = React.forwardRef<HTMLDivElement, ScrollAreaProps>(
  ({ axis = "y", maxHeight, className, style, children, ...rest }, ref) => (
    <div
      ref={ref}
      className={cn("fw-scroll min-h-0", overflow[axis], className)}
      style={maxHeight !== undefined ? { maxHeight, ...style } : style}
      {...rest}
    >
      {children}
    </div>
  ),
);
ScrollArea.displayName = "ScrollArea";
