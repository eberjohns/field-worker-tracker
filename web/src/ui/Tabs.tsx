import React, { useId, useRef } from "react";
import { CountBadge } from "./Badge";
import { cn } from "./cn";
import { nextEnabledIndex } from "./keyboard";

export interface TabItem {
  id: string;
  label: React.ReactNode;
  /** A count bubble after the label (hidden at 0). */
  count?: number;
  icon?: React.ReactNode;
  disabled?: boolean;
}

export interface TabsProps {
  tabs: readonly TabItem[];
  value: string;
  onChange: (id: string) => void;
  /** Used to link each tab to its panel (`tabPanelId`). */
  idBase?: string;
  size?: "sm" | "md";
  className?: string;
  "aria-label"?: string;
}

export function tabId(base: string, id: string): string {
  return `${base}-tab-${id}`;
}

export function tabPanelId(base: string, id: string): string {
  return `${base}-panel-${id}`;
}

/** Underlined tabs with arrow-key navigation (automatic activation). */
export const Tabs: React.FC<TabsProps> = ({ tabs, value, onChange, idBase, size = "md", className, "aria-label": ariaLabel }) => {
  const auto = useId();
  const base = idBase ?? auto;
  const refs = useRef<Array<HTMLButtonElement | null>>([]);
  const current = Math.max(
    0,
    tabs.findIndex((t) => t.id === value),
  );
  const onKeyDown = (e: React.KeyboardEvent) => {
    const next = nextEnabledIndex(tabs, current, e.key, "horizontal");
    if (next === null) return;
    e.preventDefault();
    onChange(tabs[next].id);
    refs.current[next]?.focus();
  };
  return (
    <div role="tablist" aria-label={ariaLabel} onKeyDown={onKeyDown} className={cn("flex gap-1 border-b border-fw-border", className)}>
      {tabs.map((t, i) => {
        const selected = t.id === value;
        return (
          <button
            key={t.id}
            ref={(el) => {
              refs.current[i] = el;
            }}
            type="button"
            role="tab"
            id={tabId(base, t.id)}
            aria-selected={selected}
            aria-controls={tabPanelId(base, t.id)}
            tabIndex={selected ? 0 : -1}
            disabled={t.disabled}
            onClick={() => onChange(t.id)}
            className={cn(
              "-mb-px inline-flex items-center gap-1.5 border-b-2 font-medium transition-colors",
              "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus focus-visible:ring-offset-1",
              size === "sm" ? "px-2 py-1.5 text-fw-xs" : "px-3 py-2 text-fw-sm",
              selected
                ? "border-fw-primary text-fw-primary-text"
                : "border-transparent text-fw-text-muted hover:border-fw-border-strong hover:text-fw-text",
              t.disabled && "cursor-not-allowed opacity-40",
            )}
          >
            {t.icon}
            {t.label}
            {t.count !== undefined && <CountBadge count={t.count} tone={selected ? "primary" : "neutral"} />}
          </button>
        );
      })}
    </div>
  );
};

export const TabPanel: React.FC<{ idBase: string; id: string; hidden?: boolean; className?: string; children: React.ReactNode }> = ({
  idBase,
  id,
  hidden,
  className,
  children,
}) => (
  <div role="tabpanel" id={tabPanelId(idBase, id)} aria-labelledby={tabId(idBase, id)} hidden={hidden} tabIndex={0} className={className}>
    {children}
  </div>
);
