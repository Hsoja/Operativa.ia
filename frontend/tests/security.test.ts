/**
 * Revisión estática del código del sitio: sin XSS por HTML crudo, sin almacenamiento de datos
 * personales en el navegador, sin llaves y sin URLs de terceros para scripts.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";

const SRC = join(__dirname, "..", "src");

function files(dir: string): string[] {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return files(path);
    return /\.(ts|tsx)$/.test(name) && !/\.test\.tsx?$/.test(name) ? [path] : [];
  });
}

const FORBIDDEN: [string, RegExp][] = [
  ["dangerouslySetInnerHTML", /dangerouslySetInnerHTML/],
  ["innerHTML/outerHTML", /\.(inner|outer)HTML\s*=/],
  ["eval / new Function", /\beval\s*\(|new\s+Function\s*\(/],
  ["localStorage/sessionStorage", /\b(localStorage|sessionStorage)\b/],
  ["llaves en variables VITE_", /VITE_\w*(KEY|SECRET|TOKEN)/],
  ["patrones de llaves", /gsk_[A-Za-z0-9]{16,}|AIza[0-9A-Za-z_-]{30,}|\bsk-[A-Za-z0-9_-]{20,}/],
  ["javascript: en enlaces", /href=["'{`]\s*javascript:/i],
];

describe("código del sitio", () => {
  const sources = files(SRC).map((path) => ({ path, text: readFileSync(path, "utf-8") }));

  it("tiene archivos que revisar", () => {
    expect(sources.length).toBeGreaterThan(10);
  });

  it.each(FORBIDDEN)("no usa %s", (_label, pattern) => {
    expect(sources.filter(({ text }) => pattern.test(text)).map(({ path }) => path)).toEqual([]);
  });

  it("los enlaces que abren otra pestaña llevan noopener noreferrer", () => {
    for (const { path, text } of sources) {
      for (const match of text.matchAll(/<a\b[^>]*target="_blank"[^>]*>/g)) {
        expect(match[0], path).toMatch(/rel="noopener noreferrer"/);
      }
    }
  });

  it("solo llama a la API propia con rutas relativas", () => {
    for (const { path, text } of sources) {
      for (const match of text.matchAll(/fetch\(\s*([^,)]+)/g)) {
        expect(match[1], path).not.toMatch(/https?:/);
      }
    }
  });
});

describe("index.html (sitio estático, sin cabeceras propias)", () => {
  const html = readFileSync(join(__dirname, "..", "index.html"), "utf-8");

  it("trae una CSP de respaldo sin unsafe-inline ni unsafe-eval", () => {
    const csp = html.match(/<meta http-equiv="Content-Security-Policy" content="([^"]+)"/)?.[1];
    expect(csp).toBeTruthy();
    expect(csp).not.toMatch(/unsafe-inline|unsafe-eval/);
    expect(csp).toMatch(/default-src 'self'/);
  });

  it("no tiene scripts inline: solo <script src=...> (CSP script-src 'self' los bloquearía)", () => {
    for (const match of html.matchAll(/<script\b([^>]*)>([\s\S]*?)<\/script>/g)) {
      const [, attrs, body] = match;
      expect(attrs, body).toMatch(/\bsrc=/);
      expect(body.trim(), attrs).toBe("");
    }
  });
});

describe("anti-iframe.js (respaldo de frame-ancestors en GitHub Pages)", () => {
  const script = readFileSync(join(__dirname, "..", "public", "anti-iframe.js"), "utf-8");

  it("no usa eval ni document.write", () => {
    expect(script).not.toMatch(/\beval\s*\(|document\.write/);
  });

  function run(topHref: { set: (v: string) => void } | null, sameWindow: boolean) {
    const selfLocation = { href: "https://site.example/page" };
    const win: Record<string, unknown> = { self: null, top: null };
    win.self = win;
    if (sameWindow) {
      win.top = win;
    } else {
      const topLocation: Record<string, unknown> = {};
      Object.defineProperty(topLocation, "href", { set: topHref!.set, get: () => "" });
      win.top = { location: topLocation };
    }
    (win as { location: unknown }).location = selfLocation;
    new Function("window", script)(win);
  }

  it("redirige la ventana superior cuando está embebido en un iframe", () => {
    const set = vi.fn();
    run({ set }, false);
    expect(set).toHaveBeenCalledWith("https://site.example/page");
  });

  it("no hace nada cuando no está embebido (top === self)", () => {
    expect(() => run(null, true)).not.toThrow();
  });
});
