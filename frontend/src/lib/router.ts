import { useEffect, useState } from "react";

export type Route = "home" | "services" | "about" | "reviews" | "contact" | "terms" | "privacy" | "notfound";

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

export const parseRoute = (hash: string): Route => {
  const path = hash.replace(/^#/, "").split("?")[0].replace(/\/$/, "");
  return ROUTES[path] ?? "notfound";
};

export function useRoute(): Route {
  const [route, setRoute] = useState<Route>(() => parseRoute(window.location.hash));
  useEffect(() => {
    const update = () => setRoute(parseRoute(window.location.hash));
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return route;
}
