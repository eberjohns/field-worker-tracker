import React from "react";
import { cn } from "./cn";

export interface PageHeaderProps {
  title: React.ReactNode;
  description?: React.ReactNode;
  /** Buttons on the right (primary action last). */
  actions?: React.ReactNode;
  /** Small items under the title: badges, the period, a count. */
  meta?: React.ReactNode;
  /** A trail above the title, e.g. links back to a list. */
  breadcrumbs?: React.ReactNode;
  className?: string;
}

/** The top of every page: one h1, a line of context, and the page's actions. */
export const PageHeader: React.FC<PageHeaderProps> = ({ title, description, actions, meta, breadcrumbs, className }) => (
  <header className={cn("flex flex-col gap-1 border-b border-fw-border pb-3", className)}>
    {breadcrumbs && <nav aria-label="Breadcrumb" className="text-fw-xs text-fw-text-subtle">{breadcrumbs}</nav>}
    <div className="flex flex-wrap items-start justify-between gap-3">
      <div className="min-w-0">
        <h1 className="truncate text-fw-xl font-semibold text-fw-text">{title}</h1>
        {description && <p className="mt-0.5 text-fw-sm text-fw-text-muted">{description}</p>}
        {meta && <div className="mt-1.5 flex flex-wrap items-center gap-1.5">{meta}</div>}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  </header>
);
