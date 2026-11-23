import { useEffect, useState } from "react";

/** Base grade codes in use, from GET /api/v1/grades (any signed-in role; codes only, no money). */
export function useGrades(token: string | null | undefined, enabled = true): string[] {
  const [grades, setGrades] = useState<string[]>([]);
  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    const headers: Record<string, string> = token ? { Authorization: `Bearer ${token}` } : {};
    fetch("/api/v1/grades", { headers })
      .then((res) => (res.ok ? res.json() : []))
      .then((data: unknown) => {
        if (!cancelled && Array.isArray(data)) setGrades(data.map(String));
      })
      .catch((err) => console.error("Failed to load grade codes", err));
    return () => {
      cancelled = true;
    };
  }, [token, enabled]);
  return grades;
}
