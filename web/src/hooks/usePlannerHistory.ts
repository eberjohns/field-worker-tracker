import { useState, useEffect, useCallback, useRef } from "react";

export interface PlannerHistoryEntry<T = any> {
  id: string;
  label: string;
  timestamp: number;
  payload: T;
}

interface StoredHistory<T> {
  past: PlannerHistoryEntry<T>[];
  future: PlannerHistoryEntry<T>[];
}

const MAX_HISTORY_STEPS = 25;
const HISTORY_TTL_MS = 24 * 60 * 60 * 1000; // 24 hours

function loadHistory<T>(storageKey: string): StoredHistory<T> {
  try {
    const raw = window.localStorage.getItem(storageKey);
    if (!raw) return { past: [], future: [] };
    const parsed = JSON.parse(raw) as StoredHistory<T>;
    const cutoff = Date.now() - HISTORY_TTL_MS;
    const past = Array.isArray(parsed.past)
      ? parsed.past.filter((e) => e && typeof e.timestamp === "number" && e.timestamp >= cutoff).slice(-MAX_HISTORY_STEPS)
      : [];
    const future = Array.isArray(parsed.future)
      ? parsed.future.filter((e) => e && typeof e.timestamp === "number" && e.timestamp >= cutoff).slice(-MAX_HISTORY_STEPS)
      : [];
    return { past, future };
  } catch {
    return { past: [], future: [] };
  }
}

function saveHistory<T>(storageKey: string, state: StoredHistory<T>): void {
  try {
    window.localStorage.setItem(storageKey, JSON.stringify(state));
  } catch {
    // Ignore storage quota errors cleanly
  }
}

interface UsePlannerHistoryOptions<T> {
  storageKey: string;
  enabled?: boolean;
  onUndo: (entry: PlannerHistoryEntry<T>) => Promise<boolean | void> | boolean | void;
  onRedo: (entry: PlannerHistoryEntry<T>) => Promise<boolean | void> | boolean | void;
}

/**
 * localStorage-backed Undo/Redo stack with Ctrl+Z / Ctrl+Y / Ctrl+Shift+Z shortcuts.
 * Capped at 25 steps and automatically expires entries older than 24 hours.
 */
export function usePlannerHistory<T>({
  storageKey,
  enabled = true,
  onUndo,
  onRedo,
}: UsePlannerHistoryOptions<T>) {
  const [history, setHistory] = useState<StoredHistory<T>>(() => loadHistory<T>(storageKey));
  const [isApplying, setIsApplying] = useState(false);

  const onUndoRef = useRef(onUndo);
  const onRedoRef = useRef(onRedo);
  onUndoRef.current = onUndo;
  onRedoRef.current = onRedo;

  // Reload if storageKey changes (e.g., user login switch)
  useEffect(() => {
    setHistory(loadHistory<T>(storageKey));
  }, [storageKey]);

  const persist = useCallback(
    (updater: (prev: StoredHistory<T>) => StoredHistory<T>) => {
      setHistory((prev) => {
        const next = updater(prev);
        saveHistory(storageKey, next);
        return next;
      });
    },
    [storageKey]
  );

  const push = useCallback(
    (label: string, payload: T) => {
      const entry: PlannerHistoryEntry<T> = {
        id: `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
        label,
        timestamp: Date.now(),
        payload,
      };
      persist((prev) => ({
        past: [...prev.past, entry].slice(-MAX_HISTORY_STEPS),
        future: [],
      }));
    },
    [persist]
  );

  const undo = useCallback(async () => {
    if (!enabled || isApplying || history.past.length === 0) return;
    const entry = history.past[history.past.length - 1];
    setIsApplying(true);
    try {
      const ok = await onUndoRef.current(entry);
      if (ok !== false) {
        persist((prev) => {
          if (prev.past.length === 0) return prev;
          const popped = prev.past[prev.past.length - 1];
          return {
            past: prev.past.slice(0, -1),
            future: [...prev.future, popped].slice(-MAX_HISTORY_STEPS),
          };
        });
      }
    } finally {
      setIsApplying(false);
    }
  }, [enabled, isApplying, history.past, persist]);

  const redo = useCallback(async () => {
    if (!enabled || isApplying || history.future.length === 0) return;
    const entry = history.future[history.future.length - 1];
    setIsApplying(true);
    try {
      const ok = await onRedoRef.current(entry);
      if (ok !== false) {
        persist((prev) => {
          if (prev.future.length === 0) return prev;
          const popped = prev.future[prev.future.length - 1];
          return {
            past: [...prev.past, popped].slice(-MAX_HISTORY_STEPS),
            future: prev.future.slice(0, -1),
          };
        });
      }
    } finally {
      setIsApplying(false);
    }
  }, [enabled, isApplying, history.future, persist]);

  const clear = useCallback(() => {
    persist(() => ({ past: [], future: [] }));
  }, [persist]);

  // Global keyboard shortcuts: Ctrl+Z (Undo) and Ctrl+Y / Ctrl+Shift+Z (Redo)
  useEffect(() => {
    if (!enabled) return;
    const handleKeyDown = (e: KeyboardEvent) => {
      const target = e.target as HTMLElement | null;
      if (
        target &&
        (target.tagName === "INPUT" ||
          target.tagName === "TEXTAREA" ||
          target.tagName === "SELECT" ||
          target.isContentEditable)
      ) {
        return;
      }
      const mod = e.ctrlKey || e.metaKey;
      if (!mod) return;
      const key = e.key.toLowerCase();
      if (key === "z" && !e.shiftKey) {
        if (history.past.length > 0) {
          e.preventDefault();
          void undo();
        }
      } else if (key === "y" || (key === "z" && e.shiftKey)) {
        if (history.future.length > 0) {
          e.preventDefault();
          void redo();
        }
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [enabled, history.past.length, history.future.length, undo, redo]);

  return {
    canUndo: enabled && history.past.length > 0 && !isApplying,
    canRedo: enabled && history.future.length > 0 && !isApplying,
    undoCount: history.past.length,
    redoCount: history.future.length,
    undoLabel: history.past.length > 0 ? history.past[history.past.length - 1].label : null,
    redoLabel: history.future.length > 0 ? history.future[history.future.length - 1].label : null,
    isApplying,
    push,
    undo,
    redo,
    clear,
  };
}
