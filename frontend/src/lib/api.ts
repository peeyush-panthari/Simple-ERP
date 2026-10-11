/**
 * Thin fetch wrapper around the FastAPI backend - mirrors the Reflex app's
 * api/client.py: attaches a Bearer token, parses RFC 9457 problem+json error
 * bodies into ApiError (including per-field detail), and stays free of React
 * (the 401-refresh-and-retry orchestration lives in the auth provider, which
 * is the only thing that holds the refresh token).
 *
 * The browser talks to the API through the same origin (`/api/v1/...`): Vite
 * proxies it in dev, a reverse proxy does in production, so there is no CORS.
 */

import { beginRequest } from "@/lib/activity";

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL as string | undefined) ?? "";

interface FieldError {
  field?: string;
  message?: string;
}

interface ProblemBody {
  title?: string;
  detail?: string;
  code?: string;
  errors?: FieldError[];
  meta?: { errors?: FieldError[]; [k: string]: unknown };
  [k: string]: unknown;
}

export class ApiError extends Error {
  readonly status: number;
  readonly body: ProblemBody;
  readonly code: string | undefined;
  readonly fieldErrors: FieldError[];
  readonly detail: string;

  constructor(status: number, body: ProblemBody | null) {
    const b = body ?? {};
    const baseDetail = b.detail || b.title || "Request failed";
    // Field detail is either top-level (validation_failed) or under meta
    // (rule_violation) - surface it instead of just the generic title.
    const fieldErrors = b.errors ?? b.meta?.errors ?? [];
    const detail = fieldErrors.length
      ? `${baseDetail}: ${fieldErrors.map((e) => (e.field ? `${e.field}: ${e.message}` : String(e.message ?? e))).join("; ")}`
      : baseDetail;
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.body = b;
    this.code = b.code;
    this.fieldErrors = fieldErrors;
    this.detail = detail;
  }

  get isAuth() {
    return this.status === 401;
  }
  get isForbidden() {
    return this.status === 403;
  }
  get isBusinessRule() {
    return this.status === 409 || this.status === 422;
  }
}

export type Params = Record<string, string | number | boolean | null | undefined>;

export interface RequestOptions {
  token?: string | null;
  json?: unknown;
  params?: Params;
  signal?: AbortSignal;
}

function buildUrl(path: string, params?: Params): string {
  const url = `${API_BASE_URL}${path}`;
  if (!params) return url;
  const qs = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== null && v !== undefined && v !== "") qs.set(k, String(v));
  }
  const s = qs.toString();
  return s ? `${url}${url.includes("?") ? "&" : "?"}${s}` : url;
}

async function send(method: string, path: string, opts: RequestOptions): Promise<Response> {
  const headers: Record<string, string> = {};
  if (opts.token) headers.Authorization = `Bearer ${opts.token}`;
  let body: string | undefined;
  if (opts.json !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.json);
  }
  let resp: Response;
  const finish = beginRequest(method === "GET");
  try {
    resp = await fetch(buildUrl(path, opts.params), { method, headers, body, signal: opts.signal });
  } catch (exc) {
    if (exc instanceof DOMException && exc.name === "AbortError") throw exc;
    throw new ApiError(0, { title: "Network error", detail: exc instanceof Error ? exc.message : String(exc), code: "NETWORK_ERROR" });
  } finally {
    finish();
  }
  if (resp.status >= 400) {
    let parsed: ProblemBody | null = null;
    try {
      parsed = (await resp.json()) as ProblemBody;
    } catch {
      parsed = null;
    }
    throw new ApiError(resp.status, parsed);
  }
  return resp;
}

export async function request<T = unknown>(method: string, path: string, opts: RequestOptions = {}): Promise<T> {
  const resp = await send(method, path, opts);
  if (resp.status === 204) return undefined as T;
  const text = await resp.text();
  return (text ? JSON.parse(text) : undefined) as T;
}

/** Binary GET (document downloads); returns the blob plus its content type and suggested filename. */
export async function getBlob(path: string, opts: RequestOptions = {}): Promise<{ blob: Blob; contentType: string; filename: string | null }> {
  const resp = await send("GET", path, opts);
  const disposition = resp.headers.get("content-disposition") ?? "";
  const match = /filename="?([^";]+)"?/.exec(disposition);
  return { blob: await resp.blob(), contentType: resp.headers.get("content-type") ?? "application/octet-stream", filename: match ? match[1] : null };
}
