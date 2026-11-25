import React from "react";
import { cn } from "./cn";

export type BadgeTone = "neutral" | "primary" | "success" | "warning" | "danger" | "info";

export interface BadgeProps extends React.HTMLAttributes<HTMLSpanElement> {
  tone?: BadgeTone;
  size?: "sm" | "md";
  /** A small dot before the label (status). */
  dot?: boolean;
}

const tones: Record<BadgeTone, { box: string; dot: string }> = {
  neutral: { box: "bg-fw-muted text-fw-text-muted border-fw-border", dot: "bg-fw-text-subtle" },
  primary: { box: "bg-fw-primary-soft text-fw-primary-text border-fw-primary/20", dot: "bg-fw-primary" },
  success: { box: "bg-fw-success-soft text-fw-success-text border-fw-success/20", dot: "bg-fw-success" },
  warning: { box: "bg-fw-warning-soft text-fw-warning-text border-fw-warning/25", dot: "bg-fw-warning" },
  danger: { box: "bg-fw-danger-soft text-fw-danger-text border-fw-danger/20", dot: "bg-fw-danger" },
  info: { box: "bg-fw-info-soft text-fw-info-text border-fw-info/20", dot: "bg-fw-info" },
};

export const Badge: React.FC<BadgeProps> = ({ tone = "neutral", size = "sm", dot, className, children, ...rest }) => (
  <span
    className={cn(
      "inline-flex items-center gap-1 rounded-full border font-medium whitespace-nowrap",
      size === "sm" ? "px-1.5 py-px text-[11px] leading-4" : "px-2 py-0.5 text-fw-xs",
      tones[tone].box,
      className,
    )}
    {...rest}
  >
    {dot && <span className={cn("h-1.5 w-1.5 rounded-full", tones[tone].dot)} aria-hidden="true" />}
    {children}
  </span>
);

/** A count bubble for tabs, menus and the sidebar ("99+" above 99). */
export const CountBadge: React.FC<{ count: number; tone?: BadgeTone; className?: string }> = ({
  count,
  tone = "danger",
  className,
}) =>
  count > 0 ? (
    <Badge tone={tone} className={cn("min-w-[1.25rem] justify-center tabular-nums", className)}>
      {count > 99 ? "99+" : count}
    </Badge>
  ) : null;
