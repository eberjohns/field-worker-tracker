/**
 * Server errors as something a person can read (Batch 10 A).
 *
 * The API answers errors as RFC 7807 problem details: `detail` (the message), `code`, and for
 * validation errors `invalid_params: [{field, reason}]`. A few older routes still send FastAPI's
 * `detail: {message, code}` or `detail: [{loc, msg}]`. Toasts, alert banners and forms show the
 * server's own message and, for a 422, one line per field.
 */

export interface FieldError {
  field: string;
  reason: string;
}

export interface ProblemInfo {
  status: number | null;
  code: string | null;
  message: string;
  fields: FieldError[];
}

export class ApiError extends Error {
  readonly status: number | null;
  readonly code: string | null;
  readonly fields: FieldError[];

  constructor(info: ProblemInfo) {
    super(info.message);
    this.name = "ApiError";
    this.status = info.status;
    this.code = info.code;
    this.fields = info.fields;
  }

  get info(): ProblemInfo {
    return { status: this.status, code: this.code, message: this.message, fields: this.fields };
  }
}

const GENERIC = "Something went wrong. Please try again.";

function isRecord(v: unknown): v is Record<string, unknown> {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function text(v: unknown): string | null {
  return typeof v === "string" && v.trim() ? v.trim() : null;
}

/** "body.date_from" -> "Date from"; "entries.0.hours" -> "Entries 1 hours". */
export function fieldLabel(field: string): string {
  const parts = field
    .split(".")
    .filter((p) => p && p !== "body" && p !== "query" && p !== "path")
    .map((p) => (/^\d+$/.test(p) ? String(Number(p) + 1) : p.replace(/_/g, " ")));
  const label = parts.join(" ").trim();
  return label ? label.charAt(0).toUpperCase() + label.slice(1) : "Value";
}

function fieldsFrom(body: Record<string, unknown>): FieldError[] {
  const out: FieldError[] = [];
  const params = body.invalid_params ?? body.errors;
  if (Array.isArray(params)) {
    for (const p of params) {
      if (!isRecord(p)) continue;
      const field = text(p.field) ?? text(p.name) ?? "";
      const reason = text(p.reason) ?? text(p.message) ?? text(p.msg) ?? "Invalid value";
      out.push({ field: fieldLabel(field), reason });
    }
  }
  if (Array.isArray(body.detail)) {
    for (const p of body.detail) {
      if (!isRecord(p)) continue;
      const loc = Array.isArray(p.loc) ? p.loc.map(String).join(".") : "";
      out.push({ field: fieldLabel(loc), reason: text(p.msg) ?? "Invalid value" });
    }
  }
  return out;
}

/** Problem details from a parsed error body (or anything else the server sent). */
export function problemFromBody(
  status: number | null,
  body: unknown,
  fallback: string = GENERIC,
): ProblemInfo {
  if (typeof body === "string") {
    return { status, code: null, message: text(body) ?? fallback, fields: [] };
  }
  if (!isRecord(body)) return { status, code: null, message: fallback, fields: [] };
  const detail = body.detail;
  const nested = isRecord(detail) ? detail : null;
  const fields = fieldsFrom(body);
  const message =
    text(detail) ??
    text(nested?.message) ??
    text(nested?.detail) ??
    text(body.message) ??
    text(body.title) ??
    (fields.length ? "Some values need attention." : fallback);
  const code = text(body.code) ?? text(nested?.code);
  return { status, code, message, fields };
}

/** Read an error response safely (JSON or text). Never throws. */
export async function problemFromResponse(
  res: Response,
  fallback: string = GENERIC,
): Promise<ProblemInfo> {
  let body: unknown = null;
  try {
    const raw = await res.text();
    try {
      body = raw ? JSON.parse(raw) : null;
    } catch {
      body = raw;
    }
  } catch {
    body = null;
  }
  const info = problemFromBody(res.status, body, fallback);
  if (!body && res.status) {
    info.message = `${fallback} (${res.status}${res.statusText ? ` ${res.statusText}` : ""})`;
  }
  return info;
}

/** Throws an ApiError with the server's message when the response is not OK. */
export async function ensureOk(res: Response, fallback: string = GENERIC): Promise<Response> {
  if (res.ok) return res;
  throw new ApiError(await problemFromResponse(res, fallback));
}

/** Any thrown value as ProblemInfo (ApiError, Error, string, problem body). */
export function describeError(err: unknown, fallback: string = GENERIC): ProblemInfo {
  if (err instanceof ApiError) return err.info;
  if (err instanceof Error) {
    return { status: null, code: null, message: text(err.message) ?? fallback, fields: [] };
  }
  return problemFromBody(null, err, fallback);
}
