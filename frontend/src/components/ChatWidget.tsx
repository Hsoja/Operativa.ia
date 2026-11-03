import { AnimatePresence, motion } from "motion/react";
import { ArrowUp, RotateCcw, X } from "lucide-react";
import { useCallback, useEffect, useRef, useState } from "react";

import { askSofia, type ChatState, WELCOME } from "../lib/sofia";
import { ParticleOrb } from "./ParticleOrb";
import { RobotHead } from "./Robot";

interface Message {
  id: number;
  from: "user" | "sofia";
  text: string;
}

const firstMessages = (): Message[] => [{ id: 0, from: "sofia", text: WELCOME.text }];

export function ChatWidget({ open, setOpen, pending, clearPending }: { open: boolean; setOpen: (value: boolean) => void; pending: string | null; clearPending: () => void }) {
  const [messages, setMessages] = useState<Message[]>(firstMessages);
  const [suggestions, setSuggestions] = useState(WELCOME.suggestions);
  const [input, setInput] = useState("");
  const [thinking, setThinking] = useState(false);
  const [hint, setHint] = useState(false);
  const stateRef = useRef<ChatState>(WELCOME.state);
  const nextId = useRef(1);
  const session = useRef(0);
  const listRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const launcherRef = useRef<HTMLButtonElement>(null);
  const wasOpen = useRef(false);

  const send = useCallback(
    async (raw: string) => {
      const text = raw.trim();
      if (!text || thinking) return;
      const current = session.current;
      setMessages((list) => [...list, { id: nextId.current++, from: "user", text }]);
      setSuggestions([]);
      setInput("");
      setThinking(true);
      const reply = await askSofia(text, stateRef.current);
      if (current !== session.current) return;
      stateRef.current = reply.state;
      setMessages((list) => [...list, { id: nextId.current++, from: "sofia", text: reply.text }]);
      setSuggestions(reply.suggestions);
      setThinking(false);
    },
    [thinking],
  );

  const reset = () => {
    session.current += 1;
    stateRef.current = WELCOME.state;
    setMessages(firstMessages());
    setSuggestions(WELCOME.suggestions);
    setThinking(false);
    setInput("");
    inputRef.current?.focus();
  };

  useEffect(() => {
    const timer = setTimeout(() => setHint(true), 2600);
    const hide = setTimeout(() => setHint(false), 11000);
    return () => {
      clearTimeout(timer);
      clearTimeout(hide);
    };
  }, []);

  useEffect(() => {
    if (open && pending) {
      clearPending();
      void send(pending);
    }
  }, [open, pending, clearPending, send]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, thinking]);

  useEffect(() => {
    if (open) {
      setHint(false);
      const timer = setTimeout(() => {
        // En teléfonos, enfocar abriría el teclado encima del chat sin que nadie lo pida
        if (window.matchMedia("(pointer: fine)").matches) inputRef.current?.focus();
      }, 320);
      const onKey = (event: KeyboardEvent) => event.key === "Escape" && setOpen(false);
      window.addEventListener("keydown", onKey);
      wasOpen.current = true;
      return () => {
        clearTimeout(timer);
        window.removeEventListener("keydown", onKey);
      };
    }
    if (wasOpen.current) {
      launcherRef.current?.focus();
      wasOpen.current = false;
    }
  }, [open, setOpen]);

  useEffect(() => {
    const isPhone = window.matchMedia("(max-width: 639px)").matches;
    document.body.style.overflow = open && isPhone ? "hidden" : "";
    return () => {
      document.body.style.overflow = "";
    };
  }, [open]);

  return (
    <>
      <AnimatePresence>
        {!open && (
          <motion.div
            className="fixed z-40 flex items-end gap-3"
            style={{ right: "max(1.1rem, env(safe-area-inset-right))", bottom: "max(1.1rem, env(safe-area-inset-bottom))" }}
            initial={{ scale: 0.5, opacity: 0 }}
            animate={{ scale: 1, opacity: 1 }}
            exit={{ scale: 0.5, opacity: 0 }}
            transition={{ type: "spring", stiffness: 280, damping: 20 }}
          >
            <AnimatePresence>
              {hint && (
                <motion.button
                  onClick={() => setOpen(true)}
                  tabIndex={-1}
                  initial={{ opacity: 0, x: 12, scale: 0.9 }}
                  animate={{ opacity: 1, x: 0, scale: 1 }}
                  exit={{ opacity: 0, x: 8, scale: 0.95 }}
                  className="glass mb-3 rounded-2xl rounded-br-sm px-4 py-2.5 text-left text-sm font-medium shadow-xl"
                >
                  Hi! Need a hand? 👋
                </motion.button>
              )}
            </AnimatePresence>
            <motion.button
              ref={launcherRef}
              onClick={() => setOpen(true)}
              aria-label="Open chat with Sofía"
              aria-expanded={open}
              whileHover={{ scale: 1.08, rotate: -4 }}
              whileTap={{ scale: 0.93 }}
              animate={{ y: [0, -6, 0] }}
              transition={{ y: { duration: 3.2, repeat: Infinity, ease: "easeInOut" } }}
              className="relative grid h-[4.6rem] w-[4.6rem] place-items-center rounded-full"
            >
              <span className="absolute inset-0 rounded-full bg-ember/40 blur-xl" />
              <span className="spin-ring absolute inset-0 rounded-full" />
              <span className="absolute inset-[3px] rounded-full bg-ink-2" />
              <motion.span
                className="absolute inset-0 rounded-full border border-ember/70"
                animate={{ scale: [1, 1.45], opacity: [0.7, 0] }}
                transition={{ duration: 2.2, repeat: Infinity, ease: "easeOut" }}
              />
              <RobotHead className="relative h-[3.15rem] w-[3.15rem]" />
            </motion.button>
          </motion.div>
        )}
      </AnimatePresence>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              className="fixed inset-0 z-40 hidden bg-black/45 backdrop-blur-[2px] sm:block"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              onClick={() => setOpen(false)}
            />
            <motion.aside
              role="dialog"
              aria-modal="true"
              aria-label="Chat with Sofía"
              initial={{ x: "100%" }}
              animate={{ x: 0 }}
              exit={{ x: "100%" }}
              transition={{ type: "spring", stiffness: 260, damping: 30 }}
              className="fixed inset-y-0 right-0 z-50 flex h-[100dvh] w-full flex-col overflow-hidden border-l border-line bg-ink-2 sm:w-[27rem]"
            >
              <header className="relative shrink-0 overflow-hidden border-b border-line px-5 pt-[max(1rem,env(safe-area-inset-top))] pb-4">
                <div className="absolute -top-16 -right-14 h-52 w-52 rounded-full bg-flame/25 blur-3xl" />
                <div className="relative flex items-center gap-3">
                  <span className="relative grid h-12 w-12 shrink-0 place-items-center rounded-full bg-ink-3 ring-1 ring-ember/50">
                    <RobotHead mood={thinking ? "thinking" : "idle"} className="h-9 w-9" />
                  </span>
                  <div className="min-w-0 flex-1">
                    <h2 className="font-semibold">Sofía</h2>
                    <p className="flex items-center gap-1.5 text-xs text-mute">
                      <span className="h-1.5 w-1.5 rounded-full bg-glow shadow-[0_0_8px_#ffb347]" />
                      {thinking ? "Thinking…" : "Prototype assistant"}
                    </p>
                  </div>
                  <button onClick={reset} aria-label="Start over" className="grid h-10 w-10 place-items-center rounded-full text-mute transition hover:bg-white/8 hover:text-cream">
                    <RotateCcw size={17} />
                  </button>
                  <button onClick={() => setOpen(false)} aria-label="Close chat" className="grid h-10 w-10 place-items-center rounded-full text-mute transition hover:bg-white/8 hover:text-cream">
                    <X size={20} />
                  </button>
                </div>
              </header>

              <div ref={listRef} className="scrollbar-thin relative flex-1 space-y-3 overflow-y-auto overscroll-contain px-5 py-5" aria-live="polite">
                <div className="pointer-events-none mx-auto -mt-2 mb-1 h-32 w-32">
                  <ParticleOrb className="h-full w-full" energy={thinking ? 1 : 0} density={0.34} />
                </div>
                {messages.map((message) => (
                  <motion.div
                    key={message.id}
                    initial={{ opacity: 0, y: 10, scale: 0.98 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    transition={{ duration: 0.28 }}
                    className={message.from === "user" ? "flex justify-end" : "flex"}
                  >
                    <p
                      className={
                        message.from === "user"
                          ? "max-w-[85%] rounded-2xl rounded-br-md px-4 py-2.5 text-[0.95rem] leading-relaxed font-medium whitespace-pre-wrap break-words text-[#170a05] [background:var(--grad)]"
                          : "max-w-[88%] rounded-2xl rounded-bl-md border border-line bg-ink-3 px-4 py-2.5 text-[0.95rem] leading-relaxed whitespace-pre-wrap break-words"
                      }
                    >
                      {message.text}
                    </p>
                  </motion.div>
                ))}
                {thinking && (
                  <div className="flex" aria-label="Sofía is typing">
                    <span className="flex gap-1.5 rounded-2xl rounded-bl-md border border-line bg-ink-3 px-4 py-3.5">
                      {[0, 1, 2].map((dot) => (
                        <motion.i
                          key={dot}
                          className="block h-2 w-2 rounded-full bg-ember"
                          animate={{ y: [0, -5, 0], opacity: [0.45, 1, 0.45] }}
                          transition={{ duration: 0.9, repeat: Infinity, delay: dot * 0.15 }}
                        />
                      ))}
                    </span>
                  </div>
                )}
                {!thinking && suggestions.length > 0 && (
                  <div className="flex flex-wrap gap-2 pt-1">
                    {suggestions.map((suggestion) => (
                      <button
                        key={suggestion}
                        onClick={() => void send(suggestion)}
                        className="min-h-10 rounded-full border border-ember/40 bg-ember/8 px-3.5 py-1.5 text-sm font-medium transition hover:border-ember hover:bg-ember/18"
                      >
                        {suggestion}
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <form
                className="shrink-0 border-t border-line px-4 pt-3 pb-[max(0.8rem,env(safe-area-inset-bottom))]"
                onSubmit={(event) => {
                  event.preventDefault();
                  void send(input);
                }}
              >
                <div className="flex items-center gap-2 rounded-full border border-line bg-white/4 py-1.5 pr-1.5 pl-4 transition focus-within:border-ember">
                  <input
                    ref={inputRef}
                    value={input}
                    onChange={(event) => setInput(event.target.value)}
                    maxLength={2000}
                    placeholder="Ask Sofía anything…"
                    aria-label="Message for Sofía"
                    autoComplete="off"
                    className="min-w-0 flex-1 bg-transparent text-base outline-none placeholder:text-faint focus-visible:outline-none"
                  />
                  <button
                    type="submit"
                    aria-label="Send message"
                    disabled={!input.trim() || thinking}
                    className="grid h-10 w-10 shrink-0 place-items-center rounded-full text-[#170a05] transition [background:var(--grad)] hover:scale-105 disabled:opacity-35 disabled:hover:scale-100"
                  >
                    <ArrowUp size={19} strokeWidth={2.6} />
                  </button>
                </div>
                <p className="mt-2 text-center text-[0.7rem] text-faint">Virtual assistant. Please don't share passwords or sensitive data.</p>
              </form>
            </motion.aside>
          </>
        )}
      </AnimatePresence>
    </>
  );
}
