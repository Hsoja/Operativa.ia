import { useEffect, useState } from "react";

export type Route = "home" | "services" | "about" | "reviews" | "contact" | "terms" | "privacy" | "book" | "notfound";

const BOOK_PATH = /^\/book\/([a-z0-9](?:[a-z0-9-]{1,38}[a-z0-9]))$/;

const ROUTES: Record<string, Route> = {
  "": "home",
  "/": "home",
  "/services": "services",
  "/about": "about",
  "/reviews": "reviews",
  "/contact": "contact",
  "/terms": "terms",
  "/privacy": "privacy",
};

const pathOf = (hash: string): string => hash.replace(/^#/, "").split("?")[0].replace(/\/$/, "");

export const parseRoute = (hash: string): Route => {
  const path = pathOf(hash);
  if (BOOK_PATH.test(path)) return "book";
  return ROUTES[path] ?? "notfound";
};

/** Slug del negocio en #/book/{slug}; null si no tiene el formato permitido. */
export const bookingSlug = (hash: string): string | null => BOOK_PATH.exec(pathOf(hash))?.[1] ?? null;

/** Parámetros después de "?" dentro del hash (#/book/sol?status=success&ref=...). */
export const hashParams = (hash: string): URLSearchParams => new URLSearchParams(hash.split("?")[1] ?? "");

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
