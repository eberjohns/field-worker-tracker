import React, { useEffect, useId, useState } from "react";
import { cn } from "./cn";
import { controlClass, describedBy, Field } from "./Field";
import { formatNumberInput, parseNumberInput } from "./numbers";

export interface NumberFieldProps {
  value: number | null;
  /** Called with the parsed number (null when empty) once the text is a valid number. */
  onChange: (value: number | null) => void;
  label?: React.ReactNode;
  hint?: React.ReactNode;
  /** An error from outside (server); a typing error is shown by the field itself. */
  error?: React.ReactNode;
  min?: number;
  max?: number;
  step?: number;
  integer?: boolean;
  /** Unit after the value ("h", "AED", "%"). */
  suffix?: React.ReactNode;
  placeholder?: string;
  required?: boolean;
  disabled?: boolean;
  size?: "sm" | "md";
  id?: string;
  name?: string;
  className?: string;
  fieldClassName?: string;
}

/**
 * Number input that never turns an empty field into 0 and explains out-of-range values. The
 * value is reported while typing when it is valid; invalid text stays visible with its error.
 */
export const NumberField: React.FC<NumberFieldProps> = ({
  value,
  onChange,
  label,
  hint,
  error,
  min,
  max,
  step,
  integer,
  suffix,
  placeholder,
  required,
  disabled,
  size = "md",
  id,
  name,
  className,
  fieldClassName,
}) => {
  const auto = useId();
  const inputId = id ?? auto;
  const [text, setText] = useState(() => formatNumberInput(value));
  const [typingError, setTypingError] = useState<string | null>(null);

  // Follow outside changes (reset, load) unless they are what the text already says.
  useEffect(() => {
    const parsed = parseNumberInput(text, { min, max, integer });
    if (parsed.value !== value) {
      setText(formatNumberInput(value));
      setTypingError(null);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const handle = (next: string) => {
    setText(next);
    const parsed = parseNumberInput(next, { min, max, integer });
    setTypingError(parsed.error);
    if (!parsed.error) onChange(parsed.value);
  };

  const shownError = error ?? typingError;
  return (
    <Field label={label} hint={hint} error={shownError} required={required} htmlFor={inputId} className={fieldClassName}>
      <div className="relative flex items-center">
        <input
          id={inputId}
          name={name}
          type="text"
          inputMode={integer ? "numeric" : "decimal"}
          value={text}
          placeholder={placeholder}
          required={required}
          disabled={disabled}
          step={step}
          aria-invalid={shownError ? true : undefined}
          aria-describedby={describedBy(inputId, hint, shownError)}
          onChange={(e) => handle(e.target.value)}
          onBlur={() => {
            const parsed = parseNumberInput(text, { min, max, integer });
            if (!parsed.error) setText(formatNumberInput(parsed.value));
          }}
          className={cn(controlClass({ invalid: Boolean(shownError), disabled, size }), "text-right tabular-nums", suffix && "pr-10", className)}
        />
        {suffix && <span className="pointer-events-none absolute right-2.5 text-fw-xs text-fw-text-subtle">{suffix}</span>}
      </div>
    </Field>
  );
};
