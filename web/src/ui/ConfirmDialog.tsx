import React, { useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";
import { Button } from "./Button";
import { Modal } from "./Modal";
import { TextArea, TextField } from "./TextField";

export type ConfirmVariant = "default" | "destructive";

export interface ConfirmInput {
  label: string;
  placeholder?: string;
  /** A reason box rather than a one-line field. */
  multiline?: boolean;
  /** The confirm button stays disabled until something is typed. */
  required?: boolean;
  initialValue?: string;
}

export interface ConfirmOptions {
  title: string;
  message?: React.ReactNode;
  confirmLabel?: string;
  cancelLabel?: string;
  variant?: ConfirmVariant;
  /** Ask for text (a reason, a name) before confirming. */
  input?: ConfirmInput;
  /** The confirm button stays disabled until exactly this text is typed (e.g. "RESET"). */
  requireText?: string;
}

export interface ConfirmDialogProps extends ConfirmOptions {
  open: boolean;
  /** Shows a spinner on the confirm button and blocks closing. */
  busy?: boolean;
  /** With `input`, receives the typed text. */
  onConfirm: (text: string) => void;
  onCancel: () => void;
}

/** True when the confirm button may be pressed. */
export function canConfirm(options: Pick<ConfirmOptions, "input" | "requireText">, text: string): boolean {
  if (options.requireText !== undefined) return text.trim() === options.requireText;
  if (options.input?.required) return text.trim().length > 0;
  return true;
}

/**
 * "Are you sure?" with two buttons. The destructive variant has a red confirm button and puts
 * focus on Cancel, so Enter never deletes by accident.
 */
export const ConfirmDialog: React.FC<ConfirmDialogProps> = ({
  open,
  busy = false,
  onConfirm,
  onCancel,
  title,
  message,
  confirmLabel,
  cancelLabel = "Cancel",
  variant = "default",
  input,
  requireText,
}) => {
  const [text, setText] = useState(input?.initialValue ?? "");
  const cancelRef = useRef<HTMLButtonElement>(null);
  const fieldRef = useRef<HTMLInputElement & HTMLTextAreaElement>(null);
  useEffect(() => {
    if (open) setText(input?.initialValue ?? "");
  }, [open, input?.initialValue]);

  const destructive = variant === "destructive";
  const asksText = Boolean(input || requireText !== undefined);
  const ok = canConfirm({ input, requireText }, text);
  const submit = () => {
    if (ok && !busy) onConfirm(text.trim());
  };

  return (
    <Modal
      open={open}
      onClose={onCancel}
      title={title}
      size="sm"
      dismissible={!busy}
      initialFocusRef={(asksText ? fieldRef : destructive ? cancelRef : undefined) as React.RefObject<HTMLElement> | undefined}
      footer={
        <>
          <Button ref={cancelRef} onClick={onCancel} disabled={busy}>
            {cancelLabel}
          </Button>
          <Button variant={destructive ? "destructive" : "primary"} onClick={submit} disabled={!ok} loading={busy}>
            {confirmLabel ?? (destructive ? "Delete" : "Confirm")}
          </Button>
        </>
      }
    >
      <form
        className="flex flex-col gap-3"
        onSubmit={(e) => {
          e.preventDefault();
          submit();
        }}
      >
        {(message || destructive) && (
          <div className="flex gap-2.5 text-fw-sm text-fw-text-muted">
            {destructive && <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-fw-danger" aria-hidden="true" />}
            <div>{message ?? "This cannot be undone."}</div>
          </div>
        )}
        {input &&
          (input.multiline ? (
            <TextArea
              ref={fieldRef}
              label={input.label}
              placeholder={input.placeholder}
              required={input.required}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          ) : (
            <TextField
              ref={fieldRef}
              label={input.label}
              placeholder={input.placeholder}
              required={input.required}
              value={text}
              onChange={(e) => setText(e.target.value)}
            />
          ))}
        {!input && requireText !== undefined && (
          <TextField
            ref={fieldRef}
            label={
              <>
                Type <span className="font-mono font-semibold text-fw-text">{requireText}</span> to confirm
              </>
            }
            autoComplete="off"
            value={text}
            onChange={(e) => setText(e.target.value)}
          />
        )}
      </form>
    </Modal>
  );
};
