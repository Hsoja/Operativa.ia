import { AnimatePresence, motion } from "motion/react";
import { ArrowRight, Clock, MessageCircle, ShieldCheck } from "lucide-react";
import { useState, type FormEvent } from "react";

import { useChat } from "../components/ChatContext";
import { RobotHead } from "../components/Robot";
import { Card, PageHero, Reveal } from "../components/ui";
import { submitLead, TOPICS, validateLead, type LeadErrors, type LeadInput, type SubmitResult } from "../lib/leads";

const FAILURES: Record<Exclude<SubmitResult, "sent">, string> = {
  invalid: "Some details didn't pass our checks. Please review them and try again.",
  rate_limited: "We've received many messages from this connection. Please try again in a few minutes.",
  error: "We couldn't send your message right now. Please try again later, or chat with Sofía.",
};

const EMPTY: LeadInput = { name: "", email: "", business: "", topic: TOPICS[0], message: "", consent: false, marketing: false };

function Field({ label, id, error, children }: { label: string; id: string; error?: string; children: React.ReactNode }) {
  return (
    <div>
      <label htmlFor={id} className="mb-2 block text-sm font-medium">
        {label}
      </label>
      {children}
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-sm text-[#ff8a70]">
          {error}
        </p>
      )}
    </div>
  );
}

export function Contact() {
  const { openChat } = useChat();
  const [form, setForm] = useState<LeadInput>(EMPTY);
  const [errors, setErrors] = useState<LeadErrors>({});
  const [status, setStatus] = useState<"idle" | "sending" | "sent" | Exclude<SubmitResult, "sent">>("idle");
  const [trap, setTrap] = useState("");

  const update = <K extends keyof LeadInput>(key: K, value: LeadInput[K]) => {
    setForm((current) => ({ ...current, [key]: value }));
    setErrors((current) => ({ ...current, [key]: undefined }));
  };

  const a11y = (key: keyof LeadInput) => ({ "aria-invalid": Boolean(errors[key]), "aria-describedby": errors[key] ? `${key}-error` : undefined });

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (status === "sending") return;
    // Campo invisible: solo un bot lo rellena; se le muestra éxito sin enviar nada
    if (trap) {
      setStatus("sent");
      return;
    }
    const found = validateLead(form);
    setErrors(found);
    if (Object.keys(found).length > 0) {
      document.getElementById(Object.keys(found)[0])?.focus();
      return;
    }
    setStatus("sending");
    const result = await submitLead(form, "contact-form");
    setStatus(result);
    if (result === "sent") setForm(EMPTY);
  };

  return (
    <>
      <PageHero
        eyebrow="Contact"
        title={
          <>
            Tell us about <span className="serif grad-text text-[1.1em]">your business</span>
          </>
        }
        lede="Share what takes up your team's time. We'll tell you honestly whether AI can help."
      />
      <section className="shell grid gap-6 lg:grid-cols-[1.5fr_1fr]">
        <Reveal>
          <Card className="p-6 sm:p-9">
            <AnimatePresence mode="wait">
              {status === "sent" ? (
                <motion.div key="sent" initial={{ opacity: 0, scale: 0.97 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0 }} className="py-10 text-center" role="status">
                  <RobotHead mood="happy" className="mx-auto h-24 w-24" />
                  <h2 className="mt-5 text-3xl font-semibold tracking-tight">Message sent!</h2>
                  <p className="mx-auto mt-3 max-w-md leading-relaxed text-mute">Thanks for writing. The team will review your message and reply by email.</p>
                  <button onClick={() => setStatus("idle")} className="btn btn-ghost mt-7">
                    Send another message
                  </button>
                </motion.div>
              ) : (
                <motion.form key="form" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }} onSubmit={(event) => void submit(event)} noValidate aria-busy={status === "sending"} className="space-y-5">
                  <div className="grid gap-5 sm:grid-cols-2">
                    <Field label="Your name" id="name" error={errors.name}>
                      <input id="name" className="field" autoComplete="name" maxLength={80} value={form.name} onChange={(e) => update("name", e.target.value)} {...a11y("name")} />
                    </Field>
                    <Field label="Email" id="email" error={errors.email}>
                      <input id="email" type="email" className="field" autoComplete="email" inputMode="email" maxLength={254} value={form.email} onChange={(e) => update("email", e.target.value)} {...a11y("email")} />
                    </Field>
                    <Field label="Business name (optional)" id="business" error={errors.business}>
                      <input id="business" className="field" autoComplete="organization" maxLength={120} value={form.business} onChange={(e) => update("business", e.target.value)} {...a11y("business")} />
                    </Field>
                    <Field label="What's this about?" id="topic" error={errors.topic}>
                      <select id="topic" className="field" value={form.topic} onChange={(e) => update("topic", e.target.value)} {...a11y("topic")}>
                        {TOPICS.map((topic) => (
                          <option key={topic}>{topic}</option>
                        ))}
                      </select>
                    </Field>
                  </div>
                  <Field label="How can we help?" id="message" error={errors.message}>
                    <textarea id="message" rows={5} className="field resize-y" maxLength={2000} value={form.message} onChange={(e) => update("message", e.target.value)} {...a11y("message")} />
                  </Field>
                  <div className="absolute -left-[9999px]" aria-hidden="true">
                    <label>
                      Leave this empty
                      <input tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} />
                    </label>
                  </div>
                  <div>
                    <label className="flex cursor-pointer items-start gap-3 text-sm leading-relaxed text-mute">
                      <input id="consent" type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-[#ff5a1f]" checked={form.consent} onChange={(e) => update("consent", e.target.checked)} {...a11y("consent")} />
                      <span>
                        I've read the{" "}
                        <a href="#/privacy" className="font-medium text-cream underline underline-offset-3">
                          Privacy Policy
                        </a>{" "}
                        and agree to my details being stored to answer this request.
                      </span>
                    </label>
                    <label className="mt-3 flex cursor-pointer items-start gap-3 text-sm leading-relaxed text-mute">
                      <input id="marketing" type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-[#ff5a1f]" checked={form.marketing === true} onChange={(e) => update("marketing", e.target.checked)} />
                      <span>Optional: send me occasional news and offers from Operativa.ia by email. I can unsubscribe at any time.</span>
                    </label>
                    {errors.consent && (
                      <p id="consent-error" role="alert" className="mt-1.5 text-sm text-[#ff8a70]">
                        {errors.consent}
                      </p>
                    )}
                  </div>
                  {(status === "invalid" || status === "rate_limited" || status === "error") && (
                    <p role="alert" className="rounded-xl border border-[#ff8a70]/40 bg-[#ff8a70]/10 px-4 py-3 text-sm">
                      {FAILURES[status]}
                    </p>
                  )}
                  <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={status === "sending"}>
                    {status === "sending" ? "Sending…" : "Send message"} <ArrowRight size={18} aria-hidden="true" />
                  </button>
                </motion.form>
              )}
            </AnimatePresence>
          </Card>
        </Reveal>
        <Reveal delay={0.1} className="space-y-4">
          <Card className="p-7">
            <MessageCircle size={24} className="text-ember" />
            <h2 className="mt-4 text-xl font-semibold tracking-tight">Prefer to chat?</h2>
            <p className="mt-2 leading-relaxed text-mute">Sofía can answer your questions and take your demo request right now.</p>
            <button onClick={() => openChat("I want to book a demo")} className="btn btn-ghost mt-5 w-full">
              Talk to Sofía
            </button>
          </Card>
          <Card className="p-7">
            <Clock size={24} className="text-ember" />
            <h2 className="mt-4 text-xl font-semibold tracking-tight">What happens next</h2>
            <p className="mt-2 leading-relaxed text-mute">We review your request, then set up a short discovery call to understand your business.</p>
          </Card>
          <Card className="p-7">
            <ShieldCheck size={24} className="text-ember" />
            <h2 className="mt-4 text-xl font-semibold tracking-tight">Your details are yours</h2>
            <p className="mt-2 leading-relaxed text-mute">We only use them to answer you. Please don't include passwords or sensitive data.</p>
          </Card>
        </Reveal>
      </section>
    </>
  );
}
