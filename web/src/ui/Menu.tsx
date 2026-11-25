import React, { useEffect, useId, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";
import { cn } from "./cn";
import { nextEnabledIndex } from "./keyboard";
import { Popover } from "./Popover";

export interface MenuAction {
  label: React.ReactNode;
  onSelect: () => void;
  icon?: React.ReactNode;
  /** Red text, for delete and similar. */
  destructive?: boolean;
  disabled?: boolean;
}

export type MenuEntry = MenuAction | "separator";

export interface MenuProps {
  items: readonly MenuEntry[];
  /** Accessible name of the trigger (and its text unless `trigger` is given). */
  label: string;
  /** Custom trigger content; default a "..." icon button. */
  trigger?: React.ReactNode;
  align?: "start" | "end";
  disabled?: boolean;
  className?: string;
}

function actions(items: readonly MenuEntry[]): MenuAction[] {
  return items.filter((i): i is MenuAction => i !== "separator");
}

/** A button that opens a short list of actions (row actions, "More"). */
export const Menu: React.FC<MenuProps> = ({ items, label, trigger, align = "end", disabled, className }) => {
  const menuId = useId();
  const triggerRef = useRef<HTMLButtonElement>(null);
  const itemRefs = useRef<Array<HTMLButtonElement | null>>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const list = actions(items);

  useEffect(() => {
    if (open) itemRefs.current[active]?.focus();
  }, [open, active]);

  const close = (focusTrigger = true) => {
    setOpen(false);
    if (focusTrigger) triggerRef.current?.focus();
  };
  const openAt = (index: number) => {
    setActive(index);
    setOpen(true);
  };
  const onMenuKey = (e: React.KeyboardEvent) => {
    if (e.key === "Tab") {
      close(false);
      return;
    }
    const next = nextEnabledIndex(list, active, e.key, "vertical");
    if (next !== null) {
      e.preventDefault();
      setActive(next);
    }
  };

  let actionIndex = -1;
  return (
    <>
      <button
        ref={triggerRef}
        type="button"
        disabled={disabled}
        aria-haspopup="menu"
        aria-expanded={open}
        aria-controls={open ? menuId : undefined}
        aria-label={trigger ? undefined : label}
        title={trigger ? undefined : label}
        onClick={() => (open ? close() : openAt(Math.max(0, nextEnabledIndex(list, -1, "Home") ?? 0)))}
        onKeyDown={(e) => {
          if (e.key === "ArrowDown" || e.key === "ArrowUp") {
            e.preventDefault();
            openAt((e.key === "ArrowDown" ? nextEnabledIndex(list, -1, "Home") : nextEnabledIndex(list, 0, "End")) ?? 0);
          }
        }}
        className={cn(
          "inline-flex h-8 items-center justify-center gap-1.5 rounded-fw-md text-fw-sm text-fw-text-muted hover:bg-fw-muted hover:text-fw-text",
          "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus disabled:cursor-not-allowed disabled:opacity-40",
          trigger ? "px-2.5" : "w-8",
          className,
        )}
      >
        {trigger ?? <MoreHorizontal className="h-4 w-4" aria-hidden="true" />}
      </button>
      <Popover
        open={open}
        onClose={() => close(false)}
        anchorRef={triggerRef as React.RefObject<HTMLElement>}
        placement={align === "end" ? "bottom-end" : "bottom-start"}
        role="presentation"
        className="min-w-[10rem] p-1"
      >
        <div id={menuId} role="menu" aria-label={label} onKeyDown={onMenuKey}>
          {items.map((entry, i) => {
            if (entry === "separator") return <div key={`sep-${i}`} role="separator" className="my-1 h-px bg-fw-border" />;
            actionIndex += 1;
            const index = actionIndex;
            return (
              <button
                key={i}
                ref={(el) => {
                  itemRefs.current[index] = el;
                }}
                type="button"
                role="menuitem"
                tabIndex={index === active ? 0 : -1}
                disabled={entry.disabled}
                onClick={() => {
                  close();
                  entry.onSelect();
                }}
                onMouseEnter={() => !entry.disabled && setActive(index)}
                className={cn(
                  "flex w-full items-center gap-2 rounded-fw-md px-2 py-1.5 text-left text-fw-sm",
                  "focus:outline-none focus:bg-fw-muted",
                  entry.destructive ? "text-fw-danger-text" : "text-fw-text",
                  entry.disabled ? "cursor-not-allowed opacity-40" : "hover:bg-fw-muted",
                )}
              >
                {entry.icon && (
                  <span className="flex h-4 w-4 shrink-0 items-center justify-center" aria-hidden="true">
                    {entry.icon}
                  </span>
                )}
                {entry.label}
              </button>
            );
          })}
        </div>
      </Popover>
    </>
  );
};
