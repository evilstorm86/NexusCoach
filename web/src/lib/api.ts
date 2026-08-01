const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
const TOKEN_KEY = "nexuscoach.token";

export const getToken = () =>
  typeof window === "undefined" ? null : localStorage.getItem(TOKEN_KEY);
export const setToken = (t: string) => localStorage.setItem(TOKEN_KEY, t);
export const clearToken = () => localStorage.removeItem(TOKEN_KEY);

export class ApiError extends Error {
  constructor(public status: number, message: string) {
    super(message);
  }
}

async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    headers: {
      ...(init.headers ?? {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
  });

  if (res.status === 401) {
    clearToken();
    if (typeof window !== "undefined" && !location.pathname.startsWith("/login")) {
      location.href = "/login";
    }
    throw new ApiError(401, "Session expired");
  }
  if (!res.ok) {
    // FastAPI puts the message in `detail`; validation errors make it an array.
    const body = await res.json().catch(() => null);
    const detail = body?.detail;
    throw new ApiError(
      res.status,
      typeof detail === "string" ? detail : (detail?.[0]?.msg ?? `Request failed (${res.status})`),
    );
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  del: (path: string) => request<void>(path, { method: "DELETE" }),
  put: <T>(path: string, body: unknown) =>
    request<T>(path, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    }),
  post: <T>(path: string, body?: unknown) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    }),
  form: <T>(path: string, fields: Record<string, string>) =>
    request<T>(path, {
      method: "POST",
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      body: new URLSearchParams(fields),
    }),
  upload: <T>(path: string, file: File) => {
    const data = new FormData();
    data.append("file", file);
    return request<T>(path, { method: "POST", body: data });
  },
};

/* ---- shapes the API returns ---- */

export type Trend = { per_week: number; r_squared: number; days: number; points: number } | null;
export type Summary = {
  facts: Record<string, { latest: number; at: string; days_of_data: number }>;
  analysis: Record<string, { smoothed: number; trend: Trend }>;
};
export type Point = { ts: string; value: number };
export type Series = {
  metric: string;
  facts: Point[];
  analysis: { smoothed: Point[]; trend: Trend };
};
export type Me = { id: number; email: string; role: string };
