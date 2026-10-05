import type { ApiErrorBody } from "@/types/api";

/** A failed API call. `component` names the backend component, for the panel error state. */
export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly component: string;

  constructor(status: number, code: string, message: string, component: string) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.component = component;
  }
}

export async function apiGet<T>(path: string, signal?: AbortSignal): Promise<T> {
  return request<T>(path, { signal, headers: { Accept: "application/json" } });
}

export async function apiPost<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, init);
  } catch (cause) {
    if (cause instanceof DOMException && cause.name === "AbortError") throw cause;
    throw new ApiError(0, "network", "The dashboard cannot reach the API", "network");
  }
  if (!response.ok) {
    let body: Partial<ApiErrorBody> = {};
    try {
      body = (await response.json()) as Partial<ApiErrorBody>;
    } catch {
      // not JSON (e.g. proxy error page); fall through to the generic message
    }
    const err = body.error;
    if (response.status === 401) {
      throw new ApiError(401, "unauthorized", "Sign-in expired; reload the page", "proxy");
    }
    throw new ApiError(
      response.status,
      err?.code ?? `http_${response.status}`,
      err?.message ?? `HTTP ${response.status}`,
      err?.component ?? "api",
    );
  }
  return (await response.json()) as T;
}
