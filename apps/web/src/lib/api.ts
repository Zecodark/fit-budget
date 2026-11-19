/**
 * Same-origin API client (`/api/v1/*`) using httpOnly session cookies.
 * Never stores tokens in localStorage and never calls AI providers directly (PRD §2.2, §7.3).
 */

import type { ApiErrorEnvelope, OpenApiPaths } from "./api-types";
import { getErrorMessage } from "./errorMessages";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "/api/v1";

export class ApiClientError extends Error {
  code: string;
  details: unknown;
  requestId: string;
  status: number;

  constructor(code: string, message: string, details: unknown, requestId: string, status: number) {
    super(getErrorMessage(code, message));
    this.code = code;
    this.details = details;
    this.requestId = requestId;
    this.status = status;
  }
}

export async function apiFetch<T = any>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const headers = new Headers(options.headers || {});
  if (options.body && !(options.body instanceof FormData) && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  const resp = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    credentials: "same-origin",
  });

  const reqId = resp.headers.get("X-Request-ID") || "";
  if (resp.status === 204) {
    return undefined as T;
  }

  let data: any = null;
  try {
    data = await resp.json();
  } catch {
    data = null;
  }

  if (!resp.ok) {
    const env = data as ApiErrorEnvelope | null;
    const err = env?.error;
    throw new ApiClientError(
      err?.code || "INTERNAL_ERROR",
      err?.message || getErrorMessage(err?.code),
      err?.details ?? [],
      err?.request_id || reqId,
      resp.status,
    );
  }
  return data as T;
}

export type ValidApiPath = keyof OpenApiPaths;

