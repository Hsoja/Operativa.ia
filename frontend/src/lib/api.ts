/**
 * Cliente de la API pública del backend propio. Sin llaves: el navegador solo conoce rutas relativas.
 * En desarrollo, Vite reenvía /api al backend; en producción, Caddy sirve sitio y API en el mismo dominio.
 */

/** Negocio dueño de este sitio. Es un identificador público, no un secreto. */
export const TENANT_SLUG = "operativa";
const BASE = `/api/v1/public/${TENANT_SLUG}`;
const TIMEOUT_MS = 20000;

export type ApiResult<T> =
  | { ok: true; status: number; data: T }
  | { ok: false; status: number; reason: "invalid" | "rate_limited" | "unavailable" | "network" };

export async function postJson<T>(path: string, body: unknown): Promise<ApiResult<T>> {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), TIMEOUT_MS);
  try {
    const response = await fetch(`${BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "omit",
      signal: controller.signal,
    });
    if (response.ok) return { ok: true, status: response.status, data: (await response.json()) as T };
    if (response.status === 422) return { ok: false, status: 422, reason: "invalid" };
    if (response.status === 429) return { ok: false, status: 429, reason: "rate_limited" };
    return { ok: false, status: response.status, reason: "unavailable" };
  } catch {
    return { ok: false, status: 0, reason: "network" };
  } finally {
    clearTimeout(timer);
  }
}
