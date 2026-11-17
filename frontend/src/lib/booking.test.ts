import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { formatMoney, isStripeCheckout, submitBooking } from "./booking";
import { bookingSlug, hashParams, parseRoute, unsubscribeTarget } from "./router";

const fetchMock = vi.fn();
const respond = (status: number, body: unknown = {}) =>
  fetchMock.mockResolvedValueOnce({ ok: status >= 200 && status < 300, status, json: async () => body });

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

const request = { service_id: 1, start: "2026-11-20T09:00", name: "Ana", email: "ana@sol.com", consent: true, marketing_consent: false };

describe("rutas de reserva", () => {
  it.each([
    ["#/book/clinica-sol", "book", "clinica-sol"],
    ["#/book/clinica-sol?status=success&ref=abc", "book", "clinica-sol"],
    ["#/book/../admin", "notfound", null],
    ["#/book/<script>", "notfound", null],
    ["#/book/A", "notfound", null],
  ])("%s", (hash, route, slug) => {
    expect(parseRoute(hash)).toBe(route);
    expect(bookingSlug(hash)).toBe(slug);
  });

  it("lee los parámetros del hash", () => {
    expect(hashParams("#/book/sol?status=success&ref=xyz").get("ref")).toBe("xyz");
  });
});

describe("redirección a Stripe", () => {
  it.each([
    ["https://checkout.stripe.com/c/pay/cs_test", true],
    ["http://checkout.stripe.com/c/pay", false],
    ["https://checkout.stripe.com.evil.example/pay", false],
    ["https://evil.example/?checkout.stripe.com", false],
    ["javascript:alert(1)", false],
    ["https://user@checkout.stripe.com/x", false],
    [42, false],
  ])("%s → %s", (url, expected) => {
    expect(isStripeCheckout(url)).toBe(expected);
  });

  it("no redirige si el servidor devuelve una URL ajena", async () => {
    respond(201, { status: "pending_payment", ref: "r".repeat(32), checkout_url: "https://evil.example/pay" });
    expect(await submitBooking("sol", request)).toEqual({ kind: "error", reason: "error" });
  });

  it("redirige a Stripe con la URL validada", async () => {
    respond(201, { status: "pending_payment", ref: "r".repeat(32), checkout_url: "https://checkout.stripe.com/c/pay/cs_1" });
    expect(await submitBooking("sol", request)).toMatchObject({ kind: "redirect", url: "https://checkout.stripe.com/c/pay/cs_1" });
    const [url, init] = fetchMock.mock.calls[0];
    expect(url).toBe("/api/v1/public/sol/bookings");
    expect(JSON.parse(init.body)).toEqual(request);
    expect(init.credentials).toBe("omit");
  });
});

describe("errores de reserva", () => {
  it.each([
    [409, "taken"],
    [503, "payments_off"],
    [422, "invalid"],
    [429, "rate_limited"],
    [502, "error"],
  ])("HTTP %i → %s", async (status, reason) => {
    respond(status as number);
    expect(await submitBooking("sol", request)).toEqual({ kind: "error", reason });
  });

  it("un slug inválido nunca llega a la red", async () => {
    expect(await submitBooking("../admin", request)).toEqual({ kind: "error", reason: "error" });
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("sin depósito queda confirmada", async () => {
    respond(201, { status: "confirmed", ref: "r".repeat(32) });
    expect(await submitBooking("sol", request)).toEqual({ kind: "confirmed", ref: "r".repeat(32) });
  });
});

it("formatea el depósito", () => {
  expect(formatMoney(2500, "cad")).toContain("25.00");
});

describe("baja de correos", () => {
  const token = "t".repeat(43);
  it("reconoce la ruta y valida el token", () => {
    expect(parseRoute(`#/unsubscribe/sol/${token}`)).toBe("unsubscribe");
    expect(unsubscribeTarget(`#/unsubscribe/sol/${token}`)).toEqual({ slug: "sol", token });
    expect(unsubscribeTarget("#/unsubscribe/sol/corto")).toBeNull();
    expect(unsubscribeTarget(`#/unsubscribe/../${token}`)).toBeNull();
  });
});
