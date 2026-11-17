/**
 * Cliente de la API pública del backend propio. Sin llaves: el navegador solo conoce rutas relativas.
 * En desarrollo, Vite reenvía /api al backend; en producción, Caddy sirve sitio y API en el mismo dominio.
 */

/** Negocio dueño de este sitio. Es un identificador público, no un secreto. */
export const TENANT_SLUG = "operativa";
const SLUG = /^[a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9])$/;
const base = (slug: string) => {
  if (!SLUG.test(slug)) throw new Error("slug inválido");
  return `/api/v1/public/${slug}`;
};
const TIMEOUT_MS = 20000;

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; reason: "invalid" | "rate_limited" | "conflict" | "not_found" | "unavailable" | "network" };

async function request<T>(path: string, init: RequestInit, slug: string): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${base(slug)}${path}`, { ...init, credentials: "omit", signal: controller.signal });
    if (response.ok) return { ok: true, status: response.status, data: (await response.json()) as T };
    const reasons: Record<number, "invalid" | "rate_limited" | "conflict" | "not_found"> = { 404: "not_found", 409: "conflict", 422: "invalid", 429: "rate_limited" };
    return { ok: false, status: response.status, reason: reasons[response.status] ?? "unavailable" };
  } catch {
    return { ok: false, status: 0, reason: "network" };
  } finally {
    clearTimeout(timer);
  }
}

export function postJson<T>(path: string, body: unknown, slug: string = TENANT_SLUG): Promise<ApiResult<T>> {
  return request<T>(path, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }, slug);
}

export function getJson<T>(path: string, slug: string = TENANT_SLUG): Promise<ApiResult<T>> {
  return request<T>(path, { method: "GET" }, slug);
}
