/**
 * Revisión estática del código del sitio: sin XSS por HTML crudo, sin almacenamiento de datos
 * personales en el navegador, sin llaves y sin URLs de terceros para scripts.
 */
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

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
