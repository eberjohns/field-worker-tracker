/**
 * App-wide dialogs and notifications (Batch 10 A). Wrap the app once in <UiProvider>, then:
 *
 *   const dialogs = useDialogs();
 *   if (!(await dialogs.confirm({ title: "Delete worksite?", variant: "destructive" }))) return;
 *   const reason = await dialogs.prompt({ title: "Reject leave", input: { label: "Reason", required: true } });
 *
 *   const toast = useToast();
 *   toast.success("Saved");
 *   toast.error(err);   // an ApiError shows the server's message and the 422 field list
 *
 * These replace window.alert / confirm / prompt (the ui-rules check refuses those).
 */
import React, { createContext, useCallback, useContext, useMemo, useReducer, useRef, useState } from "react";
import { ConfirmDialog, type ConfirmOptions } from "./ConfirmDialog";
import { describeError } from "./errors";
import { Toaster } from "./Toaster";
import { makeToast, toastReducer, type ToastInput } from "./toastStore";

export interface Dialogs {
  /** Resolves true when confirmed, false when cancelled. */
  confirm: (options: ConfirmOptions) => Promise<boolean>;
  /** Asks for text; resolves with it, or null when cancelled. Needs `input`. */
  prompt: (options: ConfirmOptions & { input: NonNullable<ConfirmOptions["input"]> }) => Promise<string | null>;
}

export interface Toasts {
  show: (input: ToastInput) => void;
  success: (title: string, message?: string) => void;
  info: (title: string, message?: string) => void;
  warning: (title: string, message?: string) => void;
  /** Accepts an ApiError, Error, string or problem body; or a title and message. */
  error: (errorOrTitle: unknown, message?: string) => void;
  dismiss: (id: number) => void;
}

const DialogsContext = createContext<Dialogs | null>(null);
const ToastsContext = createContext<Toasts | null>(null);

interface Pending {
  id: number;
  options: ConfirmOptions;
  resolve: (text: string | null) => void;
}

export const UiProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [toasts, dispatch] = useReducer(toastReducer, []);
  const nextId = useRef(1);
  const nextDialogId = useRef(1);
  const [queue, setQueue] = useState<Pending[]>([]);

  // One dialog at a time; later requests wait their turn.
  const ask = useCallback(
    (options: ConfirmOptions) =>
      new Promise<string | null>((resolve) => {
        const id = nextDialogId.current;
        nextDialogId.current += 1;
        setQueue((q) => [...q, { id, options, resolve }]);
      }),
    [],
  );

  const dialogs = useMemo<Dialogs>(
    () => ({
      confirm: async (options) => (await ask(options)) !== null,
      prompt: (options) => ask(options),
    }),
    [ask],
  );

  const dismiss = useCallback((id: number) => dispatch({ type: "dismiss", id }), []);
  const toastApi = useMemo<Toasts>(() => {
    const show = (input: ToastInput) => {
      const id = nextId.current;
      nextId.current += 1;
      dispatch({ type: "add", toast: makeToast(id, input) });
    };
    return {
      show,
      success: (title, message) => show({ tone: "success", title, message }),
      info: (title, message) => show({ tone: "info", title, message }),
      warning: (title, message) => show({ tone: "warning", title, message }),
      error: (errorOrTitle, message) => {
        if (typeof errorOrTitle === "string") {
          show({ tone: "error", title: errorOrTitle, message });
          return;
        }
        const info = describeError(errorOrTitle);
        show({ tone: "error", title: message ?? info.message, message: message ? info.message : undefined, fields: info.fields });
      },
      dismiss,
    };
  }, [dismiss]);

  const current = queue[0];
  return (
    <DialogsContext.Provider value={dialogs}>
      <ToastsContext.Provider value={toastApi}>
        {children}
        <Toaster toasts={toasts} onDismiss={dismiss} />
        {current && (
          <ConfirmDialog
            key={current.id}
            open
            {...current.options}
            onConfirm={(text) => {
              current.resolve(text);
              setQueue((q) => q.filter((p) => p.id !== current.id));
            }}
            onCancel={() => {
              current.resolve(null);
              setQueue((q) => q.filter((p) => p.id !== current.id));
            }}
          />
        )}
      </ToastsContext.Provider>
    </DialogsContext.Provider>
  );
};

export function useDialogs(): Dialogs {
  const ctx = useContext(DialogsContext);
  if (!ctx) throw new Error("useDialogs needs <UiProvider> around the app");
  return ctx;
}

export function useToast(): Toasts {
  const ctx = useContext(ToastsContext);
  if (!ctx) throw new Error("useToast needs <UiProvider> around the app");
  return ctx;
}
