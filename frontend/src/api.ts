import type { ApiFailure } from "./types";

const ACCESS_CODE_KEY = "vas2font-access-code";

export interface ApiRequestInit extends RequestInit {
  jsonBody?: unknown;
}

export class ApiError extends Error {
  status: number;
  code: string;
  details?: unknown;

  constructor(status: number, failure: ApiFailure) {
    super(failure.message);
    this.status = status;
    this.code = failure.code;
    this.details = failure.details;
  }
}

export function getAccessCode(): string {
  return sessionStorage.getItem(ACCESS_CODE_KEY) ?? "";
}

export function setAccessCode(code: string): void {
  sessionStorage.setItem(ACCESS_CODE_KEY, code);
}

export function clearAccessCode(): void {
  sessionStorage.removeItem(ACCESS_CODE_KEY);
}

function headers(): HeadersInit {
  const code = getAccessCode();
  return code ? { Authorization: `Bearer ${code}` } : {};
}

async function failure(response: Response): Promise<ApiError> {
  let body: ApiFailure;
  try {
    body = (await response.json()) as ApiFailure;
  } catch {
    body = {
      code: "request_failed",
      message: "The server could not complete the request",
    };
  }
  return new ApiError(response.status, body);
}

export async function api<T>(path: string, init: ApiRequestInit = {}): Promise<T> {
  const requestHeaders = new Headers(init.headers);
  const accessHeaders = new Headers(headers());
  accessHeaders.forEach((value, key) => {
    requestHeaders.set(key, value);
  });
  if (init.jsonBody !== undefined) {
    requestHeaders.set("Content-Type", "application/json");
  }
  const { jsonBody, ...requestInit } = init;
  const response = await fetch(path, {
    ...requestInit,
    headers: requestHeaders,
    body: jsonBody === undefined ? init.body : JSON.stringify(jsonBody),
  });
  if (!response.ok) throw await failure(response);
  return (await response.json()) as T;
}

export async function apiBlob(path: string, init: RequestInit = {}): Promise<Response> {
  const requestHeaders = new Headers(init.headers);
  new Headers(headers()).forEach((value, key) => {
    requestHeaders.set(key, value);
  });
  const response = await fetch(path, { ...init, headers: requestHeaders });
  if (!response.ok) throw await failure(response);
  return response;
}

export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export function formatDate(value: string): string {
  return new Intl.DateTimeFormat("en", {
    year: "numeric",
    month: "short",
    day: "numeric",
  }).format(new Date(value));
}

export function formatBytes(value: number): string {
  if (value < 1024) return `${value} B`;
  if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)} KB`;
  return `${(value / (1024 * 1024)).toFixed(1)} MB`;
}
