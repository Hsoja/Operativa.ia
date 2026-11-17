import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import { defineConfig } from "vite";

/**
 * La misma CSP que aplica deploy/Caddyfile en producción. `vite preview` la usa para probar el build
 * con las reglas reales. El servidor de desarrollo no la lleva: el recargado en caliente usa scripts inline.
 */
export const CSP = [
  "default-src 'self'",
  "script-src 'self'",
  "style-src 'self'",
  "img-src 'self' data:",
  "font-src 'self'",
  "connect-src 'self'",
  "object-src 'none'",
  "base-uri 'none'",
  "form-action 'self'",
  "frame-ancestors 'none'",
].join("; ");

const SECURITY_HEADERS = {
  "Content-Security-Policy": CSP,
  "X-Content-Type-Options": "nosniff",
  "X-Frame-Options": "DENY",
  "Referrer-Policy": "no-referrer",
  "Permissions-Policy": "camera=(), microphone=(), geolocation=(), payment=()",
};

export default defineConfig({
  plugins: [react(), tailwindcss()],
  build: {
    // Las fuentes se sirven como archivo, nunca como data:, para mantener font-src 'self' sin excepciones
    assetsInlineLimit: (file) => (/\.(woff2?|ttf|otf)$/.test(file) ? false : undefined),
  },
  server: {
    port: 5173,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
  preview: {
    port: 4173,
    headers: SECURITY_HEADERS,
    proxy: { "/api": "http://127.0.0.1:8000" },
  },
});
