/** Calls to the FastAPI back end, served under the app's base path at /compliance/api. */
export const BASE = "/compliance"; // next.config.ts basePath

type Params = Record<string, string | undefined>;

function query(params?: Params): string {
  const q = new URLSearchParams();
  for (const [k, v] of Object.entries(params ?? {})) if (v) q.set(k, v);
  const s = q.toString();
  return s ? `?${s}` : "";
}

/** A URL for a download or a link, e.g. fileUrl("/supplier-pdf", {supplier, month}). */
export const fileUrl = (path: string, params?: Params): string => `${BASE}/api${path}${query(params)}`;

/** A file the back end wrote, by its path relative to OUTPUT_DIR. */
export const outputUrl = (rel: string): string => fileUrl(`/output/${rel.split("/").map(encodeURIComponent).join("/")}`);

/** The API's message from a failed response ({"error": ...}), or the status text. */
export async function errorText(res: Response): Promise<string> {
  try {
    const body = await res.json();
    if (body && typeof body.error === "string") return body.error;
  } catch {}
  return res.statusText || `Request failed (${res.status})`;
}

export async function apiGet<T>(path: string, params?: Params): Promise<T> {
  const res = await fetch(fileUrl(path, params), { cache: "no-store" });
  if (!res.ok) throw new Error(await errorText(res));
  return res.json() as Promise<T>;
}

/** POST a form. The caller reads the Response (a 409 means another job is running). */
export const apiPost = (path: string, body: FormData | URLSearchParams): Promise<Response> =>
  fetch(fileUrl(path), { method: "POST", body });
