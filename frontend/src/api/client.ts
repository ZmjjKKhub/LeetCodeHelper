import type {
  AttemptCreateIn,
  HistoryOut,
  MetaOut,
  ProgressOut,
  TodayItemOut,
  TodayOut,
} from "./types";

// The SPA is served by the same FastAPI process it talks to (spec C5 --
// one process), so relative /api/... URLs always resolve correctly
// without a base-URL config, both under `npm run dev`'s own port (proxied
// -- see vite.config.ts's server.proxy) and once built and served by
// uvicorn itself.

// Thrown for any non-2xx /api/* response. Carries the parsed JSON body
// (FastAPI's own {detail: ...} shape for 404/422/503, see
// app_factory.py's exception handlers and schemas.py's AttemptCreateIn)
// so callers can branch on `status` and show the server's own message
// instead of a generic "request failed".
export class ApiError extends Error {
  status: number;
  detail: unknown;

  constructor(status: number, detail: unknown) {
    super(
      `API request failed: ${status}${
        typeof detail === "string" ? ` -- ${detail}` : ""
      }`,
    );
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

async function parseDetail(response: Response): Promise<unknown> {
  try {
    const body = await response.json();
    return body?.detail ?? body;
  } catch {
    return undefined;
  }
}

async function getJson<T>(url: string): Promise<T> {
  const response = await fetch(url);
  if (!response.ok) {
    throw new ApiError(response.status, await parseDetail(response));
  }
  return (await response.json()) as T;
}

export async function fetchMeta(): Promise<MetaOut> {
  return getJson<MetaOut>("/api/meta");
}

export async function fetchToday(date?: string): Promise<TodayOut> {
  const url = date ? `/api/today?date=${encodeURIComponent(date)}` : "/api/today";
  return getJson<TodayOut>(url);
}

export async function fetchHistory(limit?: number): Promise<HistoryOut> {
  const url = limit ? `/api/history?limit=${limit}` : "/api/history";
  return getJson<HistoryOut>(url);
}

export async function fetchProgress(date?: string): Promise<ProgressOut> {
  const url = date ? `/api/progress?date=${encodeURIComponent(date)}` : "/api/progress";
  return getJson<ProgressOut>(url);
}

export async function postAttempt(body: AttemptCreateIn): Promise<TodayItemOut> {
  const response = await fetch("/api/attempts", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!response.ok) {
    throw new ApiError(response.status, await parseDetail(response));
  }
  return (await response.json()) as TodayItemOut;
}
