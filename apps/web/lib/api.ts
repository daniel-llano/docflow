export type JobStatus = "queued" | "processing" | "completed" | "failed";

export interface ExtractResult {
  word_count: number;
  reading_minutes: number;
  language: string;
  keywords: string[];
  amounts: string[];
  dates: string[];
  pii: { email: number; phone: number; card: number; iban: number };
  pii_masked: boolean;
  summary: string;
  masked_preview: string;
}

export interface Job {
  id: string;
  title: string;
  filename: string | null;
  status: JobStatus;
  attempts: number;
  result: ExtractResult | null;
  error: string | null;
  createdAt: string;
  finishedAt: string | null;
}

export interface JobPage {
  items: Job[];
  total: number;
}

export interface Session {
  token: string;
  expiresAt: string;
  email: string;
}

const sessionKey = "docflow.session";

export class ApiError extends Error {
  constructor(
    readonly status: number,
    message: string,
  ) {
    super(message);
  }
}

export function loadSession(): Session | null {
  try {
    const raw = localStorage.getItem(sessionKey);
    if (!raw) return null;
    const session = JSON.parse(raw) as Session;
    return new Date(session.expiresAt).getTime() > Date.now() ? session : null;
  } catch {
    return null;
  }
}

export function saveSession(session: Session | null) {
  if (session) localStorage.setItem(sessionKey, JSON.stringify(session));
  else localStorage.removeItem(sessionKey);
}

function describe(detail: unknown, status: number): string {
  if (typeof detail === "string") return detail;
  // FastAPI validation errors come back as a list of {loc, msg}.
  if (Array.isArray(detail) && detail.length) {
    return detail.map((d: { msg?: string }) => (d.msg ?? "").replace(/^Value error, /, "")).join(" ");
  }
  return status === 429 ? "Too many requests. Wait a moment." : `Request failed (${status}).`;
}

export async function request<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (typeof init.body === "string") headers.set("Content-Type", "application/json");
  const session = loadSession();
  if (session) headers.set("Authorization", `Bearer ${session.token}`);

  let res: Response;
  try {
    res = await fetch(path, { ...init, headers });
  } catch {
    throw new ApiError(0, "Can't reach the server. Check your connection.");
  }
  const text = await res.text();
  const body = text ? JSON.parse(text) : undefined;
  if (!res.ok) throw new ApiError(res.status, describe(body?.detail, res.status));
  return body as T;
}

export const api = {
  login: (email: string, password: string) =>
    request<Session>("/api/auth/login", { method: "POST", body: JSON.stringify({ email, password }) }),
  register: (email: string, password: string) =>
    request<Session>("/api/auth/register", { method: "POST", body: JSON.stringify({ email, password }) }),
  jobs: (status: JobStatus | "", offset: number, limit = 10) =>
    request<JobPage>(`/api/jobs?limit=${limit}&offset=${offset}${status ? `&status=${status}` : ""}`),
  submitText: (title: string, text: string) =>
    request<Job>("/api/jobs", { method: "POST", body: JSON.stringify({ title, text }) }),
  submitFile: (file: File, title: string) => {
    const form = new FormData();
    form.append("file", file);
    if (title.trim()) form.append("title", title.trim());
    return request<Job>("/api/jobs/upload", { method: "POST", body: form });
  },
  remove: (id: string) => request<void>(`/api/jobs/${id}`, { method: "DELETE" }),
  retry: (id: string) => request<Job>(`/api/jobs/${id}/retry`, { method: "POST" }),
};
