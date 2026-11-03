import { AnimatePresence, motion } from "motion/react";
import { ArrowUpRight, Menu, X } from "lucide-react";
import { useEffect, useState, type ReactNode } from "react";

import type { Route } from "../lib/router";
import { useChat } from "./ChatContext";
import { Logo } from "./Logo";

const NAV: { label: string; href: string; route: Route }[] = [
  { label: "Home", href: "#/", route: "home" },
  { label: "Services", href: "#/services", route: "services" },
  { label: "About", href: "#/about", route: "about" },
  { label: "Reviews", href: "#/reviews", route: "reviews" },
  { label: "Contact", href: "#/contact", route: "contact" },
];

export function Header({ route }: { route: Route }) {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => setOpen(false), [route]);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    document.body.style.overflow = open ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <header className="fixed inset-x-0 top-0 z-30 px-3 pt-3 sm:pt-4">
      <motion.nav
        aria-label="Main"
        initial={{ y: -24, opacity: 0 }}
        animate={{ y: 0, opacity: 1 }}
        transition={{ duration: 0.7, ease: [0.2, 0.7, 0.2, 1] }}
        className={`mx-auto flex h-15 max-w-5xl items-center justify-between rounded-full border py-2 pr-2 pl-5 transition-all duration-300 ${
          scrolled || open ? "glass border-line !bg-ink-2/80 shadow-2xl shadow-black/40" : "border-transparent"
        }`}
      >
        <a href="#/" aria-label="Operativa.ia home" className="relative z-10">
          <Logo />
        </a>
        <ul className="hidden items-center gap-1 md:flex">
          {NAV.map((item) => (
            <li key={item.route}>
              <a
                href={item.href}
                aria-current={route === item.route ? "page" : undefined}
                className={`relative block rounded-full px-3.5 py-2 text-sm font-medium transition-colors ${route === item.route ? "text-cream" : "text-mute hover:text-cream"}`}
              >
                {route === item.route && <motion.span layoutId="nav-pill" className="absolute inset-0 rounded-full bg-white/9" transition={{ type: "spring", stiffness: 340, damping: 30 }} />}
                <span className="relative">{item.label}</span>
              </a>
            </li>
          ))}
        </ul>
        <a href="#/contact" className="btn btn-primary hidden !min-h-11 !py-2 !text-sm md:inline-flex">
          Book a demo <ArrowUpRight size={16} />
        </a>
        <button
          onClick={() => setOpen((value) => !value)}
          aria-label={open ? "Close menu" : "Open menu"}
          aria-expanded={open}
          className="relative z-10 grid h-11 w-11 place-items-center rounded-full bg-white/8 md:hidden"
        >
          {open ? <X size={20} /> : <Menu size={20} />}
        </button>
      </motion.nav>

      <AnimatePresence>
        {open && (
          <motion.div
            initial={{ opacity: 0, y: -10, scale: 0.98 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: -10, scale: 0.98 }}
            transition={{ duration: 0.2 }}
            className="glass mx-auto mt-2 max-w-5xl rounded-3xl bg-ink-2/90 p-3 md:hidden"
          >
            {NAV.map((item) => (
              <a
                key={item.route}
                href={item.href}
                onClick={() => setOpen(false)}
                aria-current={route === item.route ? "page" : undefined}
                className={`block rounded-2xl px-4 py-3.5 text-lg font-medium ${route === item.route ? "bg-white/9" : ""}`}
              >
                {item.label}
              </a>
            ))}
            <a href="#/contact" onClick={() => setOpen(false)} className="btn btn-primary mt-2 w-full">
              Book a demo <ArrowUpRight size={16} />
            </a>
          </motion.div>
        )}
      </AnimatePresence>
    </header>
  );
}

const FOOTER: { title: string; links: { label: string; href: string }[] }[] = [
  {
    title: "Company",
    links: [
      { label: "Services", href: "#/services" },
      { label: "About", href: "#/about" },
      { label: "Reviews", href: "#/reviews" },
      { label: "Contact", href: "#/contact" },
    ],
  },
  {
    title: "Legal",
    links: [
      { label: "Terms & Conditions", href: "#/terms" },
      { label: "Privacy Policy", href: "#/privacy" },
    ],
  },
];

export function Footer() {
  const { openChat } = useChat();
  return (
    <footer className="relative mt-24 overflow-hidden border-t border-line">
      <div className="absolute -bottom-52 left-1/2 h-96 w-[60rem] max-w-full -translate-x-1/2 rounded-full bg-flame/20 blur-[110px]" />
      <div className="shell relative grid gap-10 py-14 md:grid-cols-[1.6fr_1fr_1fr]">
        <div>
          <Logo />
          <p className="mt-4 max-w-sm text-sm leading-relaxed text-mute">AI that fits your business, not the other way around.</p>
          <button onClick={() => openChat()} className="btn btn-ghost mt-6 !min-h-11 !py-2 !text-sm">
            Talk to Sofía
          </button>
        </div>
        {FOOTER.map((column) => (
          <nav key={column.title} aria-label={column.title}>
            <h2 className="text-xs font-semibold tracking-[0.14em] text-faint uppercase">{column.title}</h2>
            <ul className="mt-4 space-y-1">
              {column.links.map((link) => (
                <li key={link.href}>
                  <a href={link.href} className="inline-block py-1.5 text-sm text-mute transition-colors hover:text-cream">
                    {link.label}
                  </a>
                </li>
              ))}
            </ul>
          </nav>
        ))}
      </div>
      <div className="shell relative flex flex-col gap-2 border-t border-line py-6 pr-20 text-xs leading-relaxed text-faint sm:flex-row sm:justify-between">
        <p>© {new Date().getFullYear()} Operativa.ia</p>
        <p>Academic prototype. Reviews and examples on this site are illustrative.</p>
      </div>
    </footer>
  );
}

export function PageTransition({ route, children }: { route: Route; children: ReactNode }) {
  return (
    <AnimatePresence mode="wait">
      <motion.main
        key={route}
        id="main"
        tabIndex={-1}
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        transition={{ duration: 0.22 }}
        onAnimationStart={(definition) => {
          if ((definition as { opacity?: number }).opacity === 1) window.scrollTo({ top: 0, behavior: "instant" as ScrollBehavior });
        }}
      >
        {children}
      </motion.main>
    </AnimatePresence>
  );
}
