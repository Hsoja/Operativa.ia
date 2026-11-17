import { ArrowRight, CalendarCheck, Clock, CreditCard, Loader2 } from "lucide-react";
import { useCallback, useEffect, useState, type FormEvent } from "react";

import { Card, PageHero } from "../components/ui";
import { formatMoney, loadCatalog, loadSlots, loadStatus, REF, submitBooking, type BookingResult, type Catalog } from "../lib/booking";
import { cleanText, isValidEmail } from "../lib/leads";
import { bookingSlug, hashParams } from "../lib/router";

const FAILURES: Record<Extract<BookingResult, { kind: "error" }>["reason"], string> = {
  taken: "That time was just taken. Please pick another one.",
  payments_off: "Online deposits aren't available right now. Please contact the business directly.",
  invalid: "Some details didn't pass our checks. Please review them.",
  rate_limited: "Too many attempts from this connection. Please try again in a few minutes.",
  error: "We couldn't complete your booking. Please try again.",
};

const STATUS_TEXT: Record<string, string> = {
  confirmed: "Your appointment is confirmed. See you soon!",
  pending_payment: "We're waiting for the payment confirmation. This page will update in a few seconds.",
  expired: "The payment window expired and the time was released. You can book again.",
  cancelled: "This booking was cancelled.",
  needs_refund: "We received your payment but need to review your booking. The business will contact you.",
};

function BookingStatus({ slug, refCode, returned }: { slug: string; refCode: string; returned: string }) {
  const [status, setStatus] = useState<string | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let attempts = 0;
    let timer: ReturnType<typeof setTimeout>;
    let active = true;
    const poll = async () => {
      const result = await loadStatus(slug, refCode);
      if (!active) return;
      if (!result.ok) {
        setFailed(true);
        return;
      }
      setStatus(result.data.status);
      // El webhook de Stripe puede tardar unos segundos en confirmar
      if (result.data.status === "pending_payment" && ++attempts < 10) timer = setTimeout(poll, 2000);
    };
    void poll();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [slug, refCode]);

  const text = failed
    ? "We couldn't find this booking."
    : returned === "cancelled" && status === "pending_payment"
      ? "You left the payment page. The time stays reserved for a few minutes; you can book again if it expires."
      : status
        ? STATUS_TEXT[status] ?? "Booking status updated."
        : "Checking your booking…";

  return (
    <Card className="p-8 text-center">
      <CalendarCheck size={36} className="mx-auto text-ember" aria-hidden="true" />
      <p role="status" aria-live="polite" className="mx-auto mt-4 max-w-md text-lg leading-relaxed">
        {text}
      </p>
      <a href={`#/book/${slug}`} className="btn btn-ghost mt-6">
        Make another booking
      </a>
    </Card>
  );
}

/** Vuelve a montar la página cuando cambia el hash (p. ej. al volver de una reserva hecha). */
export function Book() {
  const [hash, setHash] = useState(window.location.hash);
  useEffect(() => {
    const update = () => setHash(window.location.hash);
    window.addEventListener("hashchange", update);
    return () => window.removeEventListener("hashchange", update);
  }, []);
  return <BookPage key={hash} hash={hash} />;
}

function BookPage({ hash }: { hash: string }) {
  const slug = bookingSlug(hash);
  const params = hashParams(hash);
  const returnedRef = params.get("ref");
  const returned = params.get("status") ?? "";

  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState(false);
  const [serviceId, setServiceId] = useState<number | null>(null);
  const [day, setDay] = useState("");
  const [slots, setSlots] = useState<string[] | null>(null);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [slot, setSlot] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [consent, setConsent] = useState(false);
  const [marketing, setMarketing] = useState(false);
  const [trap, setTrap] = useState("");
  const [sending, setSending] = useState(false);
  const [message, setMessage] = useState("");
  const [confirmedRef, setConfirmedRef] = useState<string | null>(null);

  useEffect(() => {
    if (!slug) return;
    void loadCatalog(slug).then((result) => {
      if (result.ok) {
        setCatalog(result.data);
        // Hoy suele quedar poco o nada por la antelación mínima: se empieza por mañana si está en rango
        const tomorrow = new Date(`${result.data.first_day}T12:00:00`);
        tomorrow.setDate(tomorrow.getDate() + 1);
        const next = tomorrow.toISOString().slice(0, 10);
        setDay(next <= result.data.last_day ? next : result.data.first_day);
        if (result.data.services.length === 1) setServiceId(result.data.services[0].id);
      } else setCatalogError(true);
    });
  }, [slug]);

  const refreshSlots = useCallback(async () => {
    if (!slug || !serviceId || !day) return;
    setSlotsLoading(true);
    setSlot("");
    const result = await loadSlots(slug, serviceId, day);
    setSlots(result.ok ? result.data.slots : []);
    setSlotsLoading(false);
  }, [slug, serviceId, day]);

  useEffect(() => {
    void refreshSlots();
  }, [refreshSlots]);

  if (!slug) return null;
  if (returnedRef && REF.test(returnedRef)) {
    return (
      <>
        <PageHero eyebrow="Booking" title="Your booking" />
        <section className="shell mx-auto max-w-2xl">
          <BookingStatus slug={slug} refCode={returnedRef} returned={returned} />
        </section>
      </>
    );
  }

  const service = catalog?.services.find((s) => s.id === serviceId) ?? null;

  const submit = async (event: FormEvent) => {
    event.preventDefault();
    if (sending) return;
    if (trap) return; // campo trampa: un bot no recibe respuesta útil
    if (!service || !slot) return setMessage("Please choose a service and a time.");
    if (cleanText(name).length < 2) return setMessage("Please enter your name.");
    if (!isValidEmail(cleanText(email))) return setMessage("Please enter a valid email address.");
    if (!consent) return setMessage("Please accept the Privacy Policy to continue.");
    setSending(true);
    setMessage("");
    const result = await submitBooking(slug, { service_id: service.id, start: slot, name: cleanText(name), email: cleanText(email), consent: true, marketing_consent: marketing });
    if (result.kind === "redirect") {
      window.location.assign(result.url);
      return;
    }
    setSending(false);
    if (result.kind === "confirmed") return setConfirmedRef(result.ref);
    setMessage(FAILURES[result.reason]);
    if (result.reason === "taken") void refreshSlots();
  };

  if (confirmedRef) {
    return (
      <>
        <PageHero eyebrow="Booking" title="Your booking" />
        <section className="shell mx-auto max-w-2xl">
          <BookingStatus slug={slug} refCode={confirmedRef} returned="success" />
        </section>
      </>
    );
  }

  return (
    <>
      <PageHero eyebrow="Booking" title="Book an appointment" lede="Choose a service and a time. If a deposit is required, you'll pay it securely on Stripe." />
      <section className="shell mx-auto max-w-3xl">
        <Card className="p-6 sm:p-9">
          {catalogError && (
            <p role="alert" className="text-center">
              This booking page isn't available. Please check the link.
            </p>
          )}
          {!catalog && !catalogError && (
            <p role="status" className="flex items-center justify-center gap-2 text-mute">
              <Loader2 size={18} className="animate-spin" aria-hidden="true" /> Loading services…
            </p>
          )}
          {catalog && catalog.services.length === 0 && <p className="text-center">Online booking isn't open yet for this business.</p>}
          {catalog && catalog.services.length > 0 && (
            <form onSubmit={(event) => void submit(event)} noValidate aria-busy={sending} className="space-y-6">
              <fieldset>
                <legend className="mb-3 text-sm font-medium">1. Service</legend>
                <div className="grid gap-3 sm:grid-cols-2">
                  {catalog.services.map((s) => (
                    <label key={s.id} className={`glass flex cursor-pointer flex-col rounded-2xl p-4 transition ${serviceId === s.id ? "ring-2 ring-ember" : ""}`}>
                      <input type="radio" name="service" className="sr-only" checked={serviceId === s.id} onChange={() => setServiceId(s.id)} />
                      <span className="font-semibold">{s.name}</span>
                      <span className="mt-1 flex items-center gap-1.5 text-sm text-mute">
                        <Clock size={14} aria-hidden="true" /> {s.duration_minutes} min
                      </span>
                      <span className="mt-1 flex items-center gap-1.5 text-sm text-mute">
                        <CreditCard size={14} aria-hidden="true" /> {s.deposit_cents > 0 ? `Deposit ${formatMoney(s.deposit_cents, s.currency)}` : "No deposit"}
                      </span>
                    </label>
                  ))}
                </div>
              </fieldset>

              <div>
                <label htmlFor="day" className="mb-2 block text-sm font-medium">
                  2. Date <span className="text-faint">({catalog.timezone})</span>
                </label>
                <input id="day" type="date" className="field" min={catalog.first_day} max={catalog.last_day} value={day} onChange={(e) => setDay(e.target.value)} />
              </div>

              <fieldset>
                <legend className="mb-3 text-sm font-medium">3. Time</legend>
                {!serviceId && <p className="text-sm text-mute">Choose a service first.</p>}
                {serviceId && slotsLoading && <p role="status" className="text-sm text-mute">Loading times…</p>}
                {serviceId && !slotsLoading && slots?.length === 0 && <p className="text-sm text-mute">No times available that day. Try another date.</p>}
                {serviceId && !slotsLoading && slots && slots.length > 0 && (
                  <div className="flex flex-wrap gap-2">
                    {slots.map((s) => (
                      <label key={s} className={`min-h-10 cursor-pointer rounded-full border px-4 py-2 text-sm font-medium transition ${slot === s ? "border-ember bg-ember/20" : "border-line"}`}>
                        <input type="radio" name="slot" className="sr-only" checked={slot === s} onChange={() => setSlot(s)} />
                        {s.slice(11)}
                      </label>
                    ))}
                  </div>
                )}
              </fieldset>

              <div className="grid gap-5 sm:grid-cols-2">
                <div>
                  <label htmlFor="book-name" className="mb-2 block text-sm font-medium">4. Your name</label>
                  <input id="book-name" className="field" autoComplete="name" maxLength={80} value={name} onChange={(e) => setName(e.target.value)} />
                </div>
                <div>
                  <label htmlFor="book-email" className="mb-2 block text-sm font-medium">Email</label>
                  <input id="book-email" type="email" className="field" autoComplete="email" maxLength={254} value={email} onChange={(e) => setEmail(e.target.value)} />
                </div>
              </div>
              <div className="absolute -left-[9999px]" aria-hidden="true">
                <label>
                  Leave this empty
                  <input tabIndex={-1} autoComplete="off" value={trap} onChange={(e) => setTrap(e.target.value)} />
                </label>
              </div>
              <label className="flex cursor-pointer items-start gap-3 text-sm leading-relaxed text-mute">
                <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-[#ff5a1f]" checked={consent} onChange={(e) => setConsent(e.target.checked)} />
                <span>
                  I've read the <a href="#/privacy" className="font-medium text-cream underline underline-offset-3">Privacy Policy</a> and agree to my name and email being stored to manage this appointment.
                </span>
              </label>
              <label className="flex cursor-pointer items-start gap-3 text-sm leading-relaxed text-mute">
                <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-[#ff5a1f]" checked={marketing} onChange={(e) => setMarketing(e.target.checked)} />
                <span>Optional: send me reminders and offers from this business by email. I can unsubscribe at any time.</span>
              </label>
              {message && (
                <p role="alert" className="rounded-xl border border-[#ff8a70]/40 bg-[#ff8a70]/10 px-4 py-3 text-sm">
                  {message}
                </p>
              )}
              <button type="submit" className="btn btn-primary w-full sm:w-auto" disabled={sending}>
                {sending ? "Booking…" : service && service.deposit_cents > 0 ? `Continue to pay ${formatMoney(service.deposit_cents, service.currency)}` : "Confirm booking"}
                <ArrowRight size={18} aria-hidden="true" />
              </button>
              <p className="text-xs text-faint">Payments are processed by Stripe. Card details never reach our servers.</p>
            </form>
          )}
        </Card>
      </section>
    </>
  );
}
