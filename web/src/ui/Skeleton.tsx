import React from "react";
import { cn } from "./cn";

export interface SkeletonProps {
  className?: string;
  width?: number | string;
  height?: number | string;
  circle?: boolean;
}

/** A grey placeholder while data loads (pulses only when motion is allowed). */
export const Skeleton: React.FC<SkeletonProps> = ({ className, width, height, circle }) => (
  <span
    aria-hidden="true"
    className={cn("block bg-fw-muted motion-safe:animate-pulse", circle ? "rounded-full" : "rounded-fw-sm", className)}
    style={{ width, height: height ?? (circle ? width : undefined) }}
  />
);

/** Lines of text; the last line is shorter. */
export const SkeletonText: React.FC<{ lines?: number; className?: string }> = ({ lines = 3, className }) => (
  <div className={cn("flex flex-col gap-2", className)} aria-hidden="true">
    {Array.from({ length: lines }, (_, i) => (
      <Skeleton key={i} className="h-3" width={i === lines - 1 && lines > 1 ? "60%" : "100%"} />
    ))}
  </div>
);

/** A table body while rows load. Announced once as "Loading". */
export const SkeletonTable: React.FC<{ rows?: number; columns?: number; className?: string }> = ({
  rows = 5,
  columns = 4,
  className,
}) => (
  <div className={cn("flex flex-col divide-y divide-fw-border", className)} role="status" aria-label="Loading">
    {Array.from({ length: rows }, (_, r) => (
      <div key={r} className="flex gap-4 px-3 py-2.5">
        {Array.from({ length: columns }, (_, c) => (
          <Skeleton key={c} className="h-3 flex-1" />
        ))}
      </div>
    ))}
  </div>
);
