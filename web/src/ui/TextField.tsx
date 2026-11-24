import React, { useId } from "react";
import { cn } from "./cn";
import { controlClass, describedBy, Field } from "./Field";

type InputProps = Omit<React.InputHTMLAttributes<HTMLInputElement>, "size">;

export interface TextFieldProps extends InputProps {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  size?: "sm" | "md";
  /** Icon or text inside the field, before the value. */
  leading?: React.ReactNode;
  /** Icon or text inside the field, after the value (a unit, a clear button). */
  trailing?: React.ReactNode;
  /** Class for the outer frame (label + control). */
  fieldClassName?: string;
}

export const TextField = React.forwardRef<HTMLInputElement, TextFieldProps>(
  ({ label, hint, error, size = "md", leading, trailing, fieldClassName, className, id, required, disabled, ...rest }, ref) => {
    const auto = useId();
    const inputId = id ?? auto;
    return (
      <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId} className={fieldClassName}>
        <div className="relative flex items-center">
          {leading && (
            <span className="pointer-events-none absolute left-2.5 flex items-center text-fw-text-subtle">{leading}</span>
          )}
          <input
            ref={ref}
            id={inputId}
            required={required}
            disabled={disabled}
            aria-invalid={error ? true : undefined}
            aria-describedby={describedBy(inputId, hint, error)}
            className={cn(controlClass({ invalid: Boolean(error), disabled, size }), leading && "pl-8", trailing && "pr-8", className)}
            {...rest}
          />
          {trailing && <span className="absolute right-2 flex items-center text-fw-text-subtle">{trailing}</span>}
        </div>
      </Field>
    );
  },
);
TextField.displayName = "TextField";

export interface TextAreaProps extends React.TextareaHTMLAttributes<HTMLTextAreaElement> {
  label?: React.ReactNode;
  hint?: React.ReactNode;
  error?: React.ReactNode;
  fieldClassName?: string;
}

export const TextArea = React.forwardRef<HTMLTextAreaElement, TextAreaProps>(
  ({ label, hint, error, fieldClassName, className, id, required, disabled, rows = 3, ...rest }, ref) => {
    const auto = useId();
    const inputId = id ?? auto;
    return (
      <Field label={label} hint={hint} error={error} required={required} htmlFor={inputId} className={fieldClassName}>
        <textarea
          ref={ref}
          id={inputId}
          rows={rows}
          required={required}
          disabled={disabled}
          aria-invalid={error ? true : undefined}
          aria-describedby={describedBy(inputId, hint, error)}
          className={cn(controlClass({ invalid: Boolean(error), disabled }), "h-auto py-1.5", className)}
          {...rest}
        />
      </Field>
    );
  },
);
TextArea.displayName = "TextArea";
