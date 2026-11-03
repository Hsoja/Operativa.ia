import { MotionConfig } from "motion/react";
import { useCallback, useEffect, useMemo, useState } from "react";

import { ChatContext } from "./components/ChatContext";
import { ChatWidget } from "./components/ChatWidget";
import { Footer, Header, PageTransition } from "./components/Layout";
import { useRoute, type Route } from "./lib/router";
import { About } from "./pages/About";
import { Contact } from "./pages/Contact";
import { Home } from "./pages/Home";
import { Privacy, Terms } from "./pages/Legal";
import { NotFound } from "./pages/NotFound";
import { Reviews } from "./pages/Reviews";
import { Services } from "./pages/Services";

const PAGES: Record<Route, { title: string; element: JSX.Element }> = {
  home: { title: "Operativa.ia — AI that fits your business", element: <Home /> },
  services: { title: "Services — Operativa.ia", element: <Services /> },
  about: { title: "About — Operativa.ia", element: <About /> },
  reviews: { title: "Reviews — Operativa.ia", element: <Reviews /> },
  contact: { title: "Contact — Operativa.ia", element: <Contact /> },
  terms: { title: "Terms & Conditions — Operativa.ia", element: <Terms /> },
  privacy: { title: "Privacy Policy — Operativa.ia", element: <Privacy /> },
  notfound: { title: "Page not found — Operativa.ia", element: <NotFound /> },
};

export function App() {
  const route = useRoute();
  const [chatOpen, setChatOpen] = useState(false);
  const [pending, setPending] = useState<string | null>(null);
  const clearPending = useCallback(() => setPending(null), []);

  const chat = useMemo(
    () => ({
      openChat: (message?: string) => {
        if (message) setPending(message);
        setChatOpen(true);
      },
    }),
    [],
  );

  useEffect(() => {
    document.title = PAGES[route].title;
  }, [route]);

  return (
    <MotionConfig reducedMotion="user">
      <ChatContext.Provider value={chat}>
        <div className="aurora" aria-hidden="true">
          <i />
          <i />
        </div>
        <div className="grain" aria-hidden="true" />
        <a href="#main" onClick={(event) => { event.preventDefault(); document.getElementById("main")?.focus(); }} className="sr-only focus:not-sr-only focus:fixed focus:top-3 focus:left-3 focus:z-50 focus:rounded-full focus:bg-cream focus:px-4 focus:py-2 focus:text-ink">
          Skip to content
        </a>
        <Header route={route} />
        <PageTransition route={route}>{PAGES[route].element}</PageTransition>
        <Footer />
        <ChatWidget open={chatOpen} setOpen={setChatOpen} pending={pending} clearPending={clearPending} />
      </ChatContext.Provider>
    </MotionConfig>
  );
}
