import React from "react";
import { Loader2 } from "lucide-react";
import { cn } from "./cn";

export type ButtonVariant = "primary" | "secondary" | "ghost" | "destructive";
export type ButtonSize = "sm" | "md";

export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: ButtonVariant;
  size?: ButtonSize;
  /** Shows a spinner and blocks clicks while an action runs. */
  loading?: boolean;
  /** Icon before the label (hidden while loading). */
  icon?: React.ReactNode;
}

const base =
  "inline-flex items-center justify-center gap-1.5 whitespace-nowrap rounded-fw-md font-medium transition-colors " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-fw-focus focus-visible:ring-offset-1 " +
  "disabled:cursor-not-allowed disabled:opacity-50";

const variants: Record<ButtonVariant, string> = {
  primary: "bg-fw-primary text-white hover:bg-fw-primary-hover",
  secondary: "border border-fw-border-strong bg-fw-surface text-fw-text hover:bg-fw-muted",
  ghost: "text-fw-text-muted hover:bg-fw-muted hover:text-fw-text",
  destructive: "bg-fw-danger text-white hover:bg-fw-danger-hover",
};

const sizes: Record<ButtonSize, string> = {
  sm: "h-7 px-2.5 text-fw-xs",
  md: "h-8 px-3 text-fw-sm",
};

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  (
    { variant = "secondary", size = "md", loading = false, icon, className, children, disabled, type = "button", ...rest },
    ref,
  ) => (
    <button
      ref={ref}
      type={type}
      disabled={disabled || loading}
      aria-busy={loading || undefined}
      className={cn(base, variants[variant], sizes[size], className)}
      {...rest}
    >
      {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : icon}
      {children}
    </button>
  ),
);
Button.displayName = "Button";

export interface IconButtonProps extends Omit<ButtonProps, "children" | "icon"> {
  /** Accessible name; also the tooltip text browsers show. */
  label: string;
  icon: React.ReactNode;
}

/** A square button with only an icon (always has an accessible name). */
export const IconButton = React.forwardRef<HTMLButtonElement, IconButtonProps>(
  ({ label, icon, variant = "ghost", size = "md", className, ...rest }, ref) => (
    <Button
      ref={ref}
      variant={variant}
      size={size}
      aria-label={label}
      title={label}
      className={cn(size === "sm" ? "w-7 px-0" : "w-8 px-0", className)}
      icon={icon}
      {...rest}
    />
  ),
);
IconButton.displayName = "IconButton";
