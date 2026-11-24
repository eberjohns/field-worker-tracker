import React, { useId } from "react";
import { ChevronDown } from "lucide-react";
import { cn } from "./cn";
import { controlClass, describedBy, Field } from "./Field";

export interface SelectOption {
  value: string;
  label: string;
  disabled?: boolean;
}

export interface SelectProps {
  value: string;
  onChange: (value: string) => void;
  options: readonly SelectOption[];
  /** First, empty choice ("Select a grade"). Omit to force a value. */
  placeholder?: string;
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  required?: boolean;
  disabled?: boolean;
  size?: "sm" | "md";
  id?: string;
  name?: string;
  className?: string;
  fieldClassName?: string;
  "aria-label"?: string;
}

/** A native select (keyboard and screen readers work as people expect) in the app's style. */
export const Select: React.FC<SelectProps> = ({
  value,
  onChange,
  options,
  placeholder,
  label,
  hint,
  error,
  required,
  disabled,
  size = "md",
  id,
  name,
  className,
  fieldClassName,
  "aria-label": ariaLabel,
}) => {
  const auto = useId();
  const selectId = id ?? auto;
  return (
    <Field label={label} hint={hint} error={error} required={required} htmlFor={selectId} className={fieldClassName}>
      <div className="relative">
        <select
          id={selectId}
          name={name}
          value={value}
          required={required}
          disabled={disabled}
          aria-label={ariaLabel}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(selectId, hint, error)}
          onChange={(e) => onChange(e.target.value)}
          className={cn(controlClass({ invalid: Boolean(error), disabled, size }), "appearance-none pr-8", className)}
        >
          {placeholder !== undefined && <option value="">{placeholder}</option>}
          {options.map((o) => (
            <option key={o.value} value={o.value} disabled={o.disabled}>
              {o.label}
            </option>
          ))}
        </select>
        <ChevronDown
          className="pointer-events-none absolute right-2 top-1/2 h-4 w-4 -translate-y-1/2 text-fw-text-subtle"
          aria-hidden="true"
        />
      </div>
    </Field>
  );
};
