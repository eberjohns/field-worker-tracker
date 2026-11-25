// Background jobs (Batch 9 step 4): start a long operation, then poll its progress.
// The server answers 202 with the job; GET /api/v1/background-jobs/{id} reports how far it is.

export type BackgroundJob = {
  id: string;
  kind: string;
  status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED" | "INTERRUPTED";
  params: Record<string, unknown>;
  phase: string | null;
  progress_done: number;
  progress_total: number;
  result: Record<string, unknown> | null;
  error_code: string | null;
  error_message: string | null;
  created_at: string;
  started_at: string | null;
  finished_at: string | null;
};

export const POLL_MS = 1000;

export function isActiveJob(job: Pick<BackgroundJob, "status">): boolean {
  return job.status === "QUEUED" || job.status === "RUNNING";
}

const PHASE_LABELS: Record<string, string> = {
  employees: "Calculating employees",
  reports: "Writing month-end reports",
};

/** "Calculating employees 120 / 580", or "Starting…" before the first progress. */
export function describeJobProgress(job: BackgroundJob): string {
  if (job.status === "QUEUED" || !job.phase) return "Starting…";
  const label = PHASE_LABELS[job.phase] ?? job.phase;
  return job.progress_total > 0 ? `${label} ${job.progress_done} / ${job.progress_total}` : label;
}

/** 0–100 across both payroll phases: employees are the first 60 %, reports the rest. */
export function jobPercent(job: BackgroundJob): number {
  if (job.status === "SUCCEEDED") return 100;
  if (!job.phase || job.progress_total <= 0) return 0;
  const part = Math.min(1, job.progress_done / job.progress_total);
  if (job.phase === "employees") return Math.round(part * 60);
  if (job.phase === "reports") return Math.round(60 + part * 40);
  return Math.round(part * 100);
}

type FetchLike = (input: string, init?: RequestInit) => Promise<Response>;

/**
 * Poll a job until it finishes. Resolves with the finished job (SUCCEEDED, FAILED or
 * INTERRUPTED); `onUpdate` sees every poll. Stops early when `signal` aborts.
 */
export async function pollJob(
  jobId: string,
  token: string | null,
  onUpdate: (job: BackgroundJob) => void,
  opts: { signal?: AbortSignal; intervalMs?: number; fetchFn?: FetchLike } = {},
): Promise<BackgroundJob | null> {
  const fetchFn = opts.fetchFn ?? fetch;
  const interval = opts.intervalMs ?? POLL_MS;
  for (;;) {
    if (opts.signal?.aborted) return null;
    const res = await fetchFn(`/api/v1/background-jobs/${jobId}`, {
      headers: token ? { Authorization: `Bearer ${token}` } : {},
    });
    if (!res.ok) throw new Error(`Job status failed (${res.status})`);
    const job = (await res.json()) as BackgroundJob;
    onUpdate(job);
    if (!isActiveJob(job)) return job;
    await new Promise((r) => setTimeout(r, interval));
  }
}
