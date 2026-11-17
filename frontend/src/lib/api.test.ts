import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { getJson, postJson } from "./api";

const fetchMock = vi.fn();
const respond = (status: number, body: unknown = {}) =>
  fetchMock.mockResolvedValueOnce({ ok: status >= 200 && status < 300, status, json: async () => body });

beforeEach(() => {
  fetchMock.mockReset();
  vi.stubGlobal("fetch", fetchMock);
});
afterEach(() => vi.unstubAllGlobals());

describe("URL base de la API", () => {
  it("usa rutas relativas por defecto (mismo origen, sin VITE_API_BASE_URL)", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "");
    respond(200, { ok: true });
    await getJson("/services", "sol");
    expect(fetchMock.mock.calls[0][0]).toBe("/api/v1/public/sol/services");
  });

  it("antepone la URL de la API cuando está configurada (sitio y API en dominios distintos)", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://operativa-api.onrender.com");
    respond(200, { ok: true });
    await getJson("/services", "sol");
    expect(fetchMock.mock.calls[0][0]).toBe("https://operativa-api.onrender.com/api/v1/public/sol/services");
  });

  it("quita la barra final para no duplicarla", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://operativa-api.onrender.com/");
    respond(200, { ok: true });
    await postJson("/contact", {}, "sol");
    expect(fetchMock.mock.calls[0][0]).toBe("https://operativa-api.onrender.com/api/v1/public/sol/contact");
  });

  it("nunca incluye una llave: la URL es pública y no lleva credenciales", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://operativa-api.onrender.com");
    respond(200, {});
    await getJson("/services", "sol");
    const init = fetchMock.mock.calls[0][1] as RequestInit;
    expect(init.credentials).toBe("omit");
    expect(JSON.stringify(init.headers ?? {})).not.toMatch(/key|token|secret/i);
  });

  it("rechaza un slug inválido sin llegar a la red", async () => {
    vi.stubEnv("VITE_API_BASE_URL", "https://operativa-api.onrender.com");
    expect(await getJson("/services", "../admin")).toEqual({ ok: false, status: 0, reason: "network" });
    expect(fetchMock).not.toHaveBeenCalled();
  });
});
