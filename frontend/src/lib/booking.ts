/**
 * Reserva pública con depósito (P2.10).
 * El navegador nunca decide montos ni URLs de retorno: solo elige servicio, hora y envía sus datos.
 */

import { getJson, postJson, type ApiResult } from "./api";

export interface Service {
  id: number;
  name: string;
  duration_minutes: number;
  deposit_cents: number;
  currency: string;
}

export interface Catalog {
  services: Service[];
  timezone: string;
  first_day: string;
  last_day: string;
}

export interface BookingRequest {
  service_id: number;
  start: string;
  name: string;
  email: string;
  consent: boolean;
  marketing_consent: boolean;
}

export type BookingResult =
  | { kind: "redirect"; url: string; ref: string }
  | { kind: "confirmed"; ref: string }
  | { kind: "error"; reason: "taken" | "payments_off" | "invalid" | "rate_limited" | "error" };

export const REF = /^[A-Za-z0-9_-]{20,64}$/;

/** Solo se redirige a Stripe Checkout por https; cualquier otra URL se descarta. */
export function isStripeCheckout(url: unknown): url is string {
  if (typeof url !== "string") return false;
  try {
    const parsed = new URL(url);
    return parsed.protocol === "https:" && (parsed.hostname === "checkout.stripe.com" || parsed.hostname.endsWith(".stripe.com")) && !parsed.username;
  } catch {
    return false;
  }
}

export function formatMoney(cents: number, currency: string, locale = "en-CA"): string {
  return new Intl.NumberFormat(locale, { style: "currency", currency: currency.toUpperCase() }).format(cents / 100);
}

export const loadCatalog = (slug: string) => getJson<Catalog>("/services", slug);

export const loadSlots = (slug: string, serviceId: number, day: string) =>
  getJson<{ slots: string[] }>(`/slots?service_id=${encodeURIComponent(serviceId)}&date=${encodeURIComponent(day)}`, slug);

export const loadStatus = (slug: string, ref: string): Promise<ApiResult<{ status: string; service: string; starts_at: number }>> =>
  getJson(`/bookings/${encodeURIComponent(ref)}`, slug);

export async function submitBooking(slug: string, request: BookingRequest): Promise<BookingResult> {
  const result = await postJson<{ status: string; ref: string; checkout_url?: string }>("/bookings", request, slug);
  if (result.ok) {
    if (result.data.status === "confirmed") return { kind: "confirmed", ref: result.data.ref };
    if (result.data.status === "pending_payment" && isStripeCheckout(result.data.checkout_url)) {
      return { kind: "redirect", url: result.data.checkout_url, ref: result.data.ref };
    }
    return { kind: "error", reason: "error" };
  }
  if (result.reason === "conflict") return { kind: "error", reason: "taken" };
  if (result.status === 503) return { kind: "error", reason: "payments_off" };
  if (result.reason === "invalid") return { kind: "error", reason: "invalid" };
  if (result.reason === "rate_limited") return { kind: "error", reason: "rate_limited" };
  return { kind: "error", reason: "error" };
}
