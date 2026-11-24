import React from "react";
import { Inbox } from "lucide-react";
import { cn } from "./cn";

export interface EmptyStateProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Defaults to an inbox icon. */
  icon?: React.ReactNode;
  /** A button or link to the next step. */
  action?: React.ReactNode;
  /** Less padding, for panels and table bodies. */
  compact?: boolean;
  className?: string;
}

/** What a list, table or report shows when there is nothing in it yet. */
export const EmptyState: React.FC<EmptyStateProps> = ({ title, description, icon, action, compact, className }) => (
  <div
    className={cn(
      "flex flex-col items-center justify-center text-center",
      compact ? "gap-1.5 px-4 py-6" : "gap-2 px-6 py-12",
      className,
    )}
  >
    <div className="flex h-10 w-10 items-center justify-center rounded-full bg-fw-muted text-fw-text-subtle" aria-hidden="true">
      {icon ?? <Inbox className="h-5 w-5" />}
    </div>
    <p className="text-fw-base font-medium text-fw-text">{title}</p>
    {description && <p className="max-w-sm text-fw-sm text-fw-text-muted">{description}</p>}
    {action && <div className="mt-2">{action}</div>}
  </div>
);
