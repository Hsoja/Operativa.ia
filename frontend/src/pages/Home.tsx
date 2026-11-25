import { motion, useScroll, useTransform } from "motion/react";
import { ArrowRight, ArrowUpRight, Check, Mic, Plus, RotateCcw, X } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { useChat } from "../components/ChatContext";
import { ParticleOrb } from "../components/ParticleOrb";
import { Robot, RobotHead } from "../components/Robot";
import { Card, PrototypeNote, Reveal, Waveform } from "../components/ui";
import { FAQS, REVIEWS, SERVICES, STEPS } from "../content/site";

const TICKER = [
  { k: "24/7", v: "lead capture" },
  { k: "48h", v: "template setup" },
  { k: "4", v: "industry templates" },
  { k: "1-click", v: "email opt-out" },
  { k: "", v: "Calendars" },
  { k: "", v: "Email" },
  { k: "", v: "Messaging" },
  { k: "", v: "Booking systems" },
];

const VOICE_LINES = ["Which days do you have openings?", "Can I move my appointment to Friday?", "Do you work with small teams?", "How do I get started?"];

function Ticker() {
  const row = [...TICKER, ...TICKER];
  return (
    <div className="hero-band marquee z-[5] overflow-hidden lg:absolute lg:inset-x-0 lg:top-[55%]">
      <div>
        {row.map((item, index) => (
          <span key={index} className="flex items-center gap-4 pr-4 text-sm font-medium tracking-wide whitespace-nowrap uppercase sm:text-base" aria-hidden={index >= TICKER.length}>
            <span className="text-[#5b4d45]">{item.v}</span>
            {item.k && <strong className="font-extrabold text-ink">{item.k}</strong>}
            <span className="text-ember" aria-hidden="true">
              //
            </span>
          </span>
        ))}
      </div>
    </div>
  );
}

function Hero() {
  const { openChat } = useChat();
  return (
    <section aria-labelledby="hero-title" className="hero-frame px-2.5 pt-2.5 pb-2.5 sm:px-5 sm:pt-5 sm:pb-5">
      <div className="stage relative mx-auto flex max-w-[96rem] flex-col overflow-hidden rounded-[1.75rem] pt-28 pb-8 sm:rounded-[2.4rem] lg:block lg:h-[58rem] lg:pt-0 lg:pb-0">
        <h1 id="hero-title" className="sr-only">
          AI that fits your business
        </h1>

        <motion.p
          aria-hidden="true"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, ease: [0.2, 0.7, 0.2, 1] }}
          className="hero-word relative z-0 px-5 sm:px-10 lg:absolute lg:top-32 lg:left-6 lg:px-8"
        >
          AI that
          <br />
          <span className="lg:ml-[0.55em]">fits</span>
        </motion.p>

        <Ticker />

        <div className="relative z-10 mx-auto -my-4 h-[21rem] sm:h-[30rem] lg:absolute lg:inset-x-0 lg:bottom-0 lg:my-0 lg:h-[92%]">
          <div className="absolute top-[52%] left-1/2 aspect-square h-[78%] -translate-x-1/2 -translate-y-1/2 rounded-full [background:radial-gradient(closest-side,rgb(255_90_31/0.38),rgb(255_90_31/0.12)_62%,transparent)]" aria-hidden="true" />
          <Robot className="relative mx-auto h-full w-auto drop-shadow-[0_26px_40px_rgba(90,30,10,0.35)]" />
        </div>

        <motion.p
          aria-hidden="true"
          initial={{ opacity: 0, y: 30 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.9, delay: 0.12, ease: [0.2, 0.7, 0.2, 1] }}
          className="hero-word relative z-20 px-5 text-right sm:px-10 lg:absolute lg:right-6 lg:bottom-6 lg:px-8"
        >
          your
          <br />
          business
        </motion.p>

        <dl className="relative z-20 mt-6 grid grid-cols-2 gap-4 px-5 sm:px-10 lg:absolute lg:top-32 lg:right-10 lg:mt-0 lg:block lg:space-y-9 lg:px-0 lg:text-right">
          {[
            ["24/7", "lead capture, even at night"],
            ["48h", "from kickoff to live assistant"],
          ].map(([value, label]) => (
            <div key={value}>
              <dt className="text-5xl font-extrabold tracking-[-0.06em] text-ink sm:text-6xl">{value}</dt>
              <dd className="mt-1 text-sm text-[#5b4d45] sm:text-base">{label}</dd>
            </div>
          ))}
        </dl>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.8, delay: 0.25 }}
          className="relative z-20 mt-8 max-w-md px-5 sm:px-10 lg:absolute lg:bottom-10 lg:left-6 lg:mt-0 lg:px-8"
        >
          <p className="text-xl leading-snug font-semibold tracking-tight text-ink sm:text-2xl">We learn how you work, customize an assistant around it and connect your tools.</p>
          <p className="mt-2 text-base text-[#5b4d45]">The chatbot is just the start.</p>
          <div className="mt-6 flex flex-wrap items-center gap-3">
            <a href="#/contact" className="stage-cta">
              Book a free demo
              <span className="stage-cta-chip">
                <ArrowUpRight size={18} aria-hidden="true" />
              </span>
            </a>
            <button onClick={() => openChat()} className="inline-flex min-h-12 items-center gap-2 rounded-full px-3 font-semibold text-ink underline decoration-ember decoration-2 underline-offset-4">
              <RobotHead className="h-7 w-7" /> Talk to Sofía
            </button>
          </div>
        </motion.div>
      </div>
    </section>
  );
}

function Value() {
  return (
    <section className="shell py-16 sm:py-24">
      <Reveal className="max-w-3xl">
        <span className="eyebrow">Why Operativa.ia</span>
        <h2 className="h2 mt-4">
          A chatbot is easy to buy. <span className="serif grad-text text-[1.08em]">Making it work for you</span> is the hard part.
        </h2>
      </Reveal>
      <div className="mt-12 grid gap-4 md:grid-cols-6">
        <Reveal className="md:col-span-4">
          <Card className="h-full min-h-[21rem] p-7 sm:p-9">
            <div className="absolute -right-20 -bottom-24 h-72 w-72 opacity-70 sm:-right-10 sm:-bottom-16 sm:h-80 sm:w-80 sm:opacity-100">
              <ParticleOrb className="h-full w-full" density={0.5} />
            </div>
            <div className="relative max-w-[19rem] sm:max-w-sm">
              <h3 className="text-2xl font-semibold tracking-tight sm:text-3xl">Built around how you already work</h3>
              <p className="mt-3 leading-relaxed text-mute">Off-the-shelf bots ask you to change your process. We begin with your real days, your real customers and the way your team likes to do things.</p>
            </div>
          </Card>
        </Reveal>
        <Reveal delay={0.08} className="md:col-span-2">
          <Card className="h-full p-7">
            <h3 className="text-xl font-semibold tracking-tight">Your tone, not a robot's</h3>
            <p className="mt-3 leading-relaxed text-mute">The assistant learns your services, your policies and how you speak to customers.</p>
            <div className="mt-6 space-y-2 text-sm">
              <p className="ml-auto w-fit rounded-2xl rounded-br-md px-3.5 py-2 font-medium text-ink [background:var(--grad)]">Are you open Sunday?</p>
              <p className="w-fit rounded-2xl rounded-bl-md border border-line bg-ink-3 px-3.5 py-2">Closed Sundays, but Monday at 9 is free. Shall I save it?</p>
            </div>
          </Card>
        </Reveal>
        <Reveal delay={0.04} className="md:col-span-2">
          <Card className="h-full p-7">
            <h3 className="text-xl font-semibold tracking-tight">People stay in charge</h3>
            <p className="mt-3 leading-relaxed text-mute">Difficult cases go to your team with the full context, so customers never get stuck.</p>
          </Card>
        </Reveal>
        <Reveal delay={0.12} className="md:col-span-4">
          <Card className="h-full p-7 sm:p-9">
            <div className="flex flex-col justify-between gap-6 sm:flex-row sm:items-center">
              <div className="max-w-md">
                <h3 className="text-xl font-semibold tracking-tight sm:text-2xl">We don't vanish after launch</h3>
                <p className="mt-3 leading-relaxed text-mute">We train your team, review conversations and update the assistant as your business changes.</p>
              </div>
              <Waveform bars={32} className="!h-14 shrink-0" />
            </div>
          </Card>
        </Reveal>
      </div>
    </section>
  );
}

function Process() {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 75%", "end 55%"] });
  const scaleX = useTransform(scrollYProgress, [0, 1], [0, 1]);
  return (
    <section className="relative overflow-hidden py-16 sm:py-24">
      <div className="shell">
        <Reveal className="mx-auto max-w-3xl text-center">
          <span className="eyebrow">How it works</span>
          <h2 className="h2 mt-4">
            Four steps from <span className="serif grad-text text-[1.08em]">first talk to everyday tool</span>
          </h2>
        </Reveal>
        <div ref={ref} className="relative mt-16">
          <div className="absolute inset-x-0 top-6 hidden h-px bg-line md:block">
            <motion.div style={{ scaleX, transformOrigin: "left" }} className="h-full w-full [background:var(--grad)]" />
          </div>
          <ol className="grid gap-8 md:grid-cols-4 md:gap-6">
            {STEPS.map((step, index) => (
              <Reveal key={step.title} delay={index * 0.08}>
                <li className="relative list-none">
                  <span className="relative grid h-12 w-12 place-items-center rounded-full border border-ember/50 bg-ink-2 font-semibold shadow-[0_0_24px_rgba(255,90,31,0.35)]">{index + 1}</span>
                  <h3 className="mt-5 text-xl font-semibold tracking-tight">{step.title}</h3>
                  <p className="mt-2 leading-relaxed text-mute">{step.text}</p>
                </li>
              </Reveal>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}

function PhoneVoice() {
  const [index, setIndex] = useState(0);
  const [chars, setChars] = useState(0);
  const line = VOICE_LINES[index];

  useEffect(() => {
    const done = chars >= line.length;
    const timer = setTimeout(
      () => {
        if (done) {
          setChars(0);
          setIndex((value) => (value + 1) % VOICE_LINES.length);
        } else {
          setChars((value) => value + 1);
        }
      },
      done ? 2100 : 42,
    );
    return () => clearTimeout(timer);
  }, [chars, line.length]);

  return (
    <div className="relative mx-auto w-full max-w-[20rem] rounded-[3rem] border border-white/15 bg-black p-3 shadow-[0_40px_90px_-25px_rgba(255,90,31,0.55)]">
      <div className="relative flex h-[33rem] flex-col overflow-hidden rounded-[2.4rem] bg-[#070403]">
        <div className="mx-auto mt-3 h-6 w-24 rounded-full bg-white/8" />
        <div className="mt-4 flex items-center gap-2.5 px-5">
          <RobotHead className="h-8 w-8" />
          <div>
            <p className="text-sm font-semibold">Sofía</p>
            <p className="text-[0.7rem] text-mute">Listening…</p>
          </div>
        </div>
        <div className="relative mt-3 flex-1">
          <ParticleOrb className="absolute inset-0 h-full w-full" density={0.55} energy={0.7} />
        </div>
        <p className="min-h-[4.2rem] px-6 text-center text-lg leading-snug font-medium" aria-hidden="true">
          {line.slice(0, chars)}
          <span className="text-ember">|</span>
          <span className="text-white/25">{line.slice(chars)}</span>
        </p>
        <div className="flex items-center justify-between px-9 pt-3 pb-7 text-mute" aria-hidden="true">
          <RotateCcw size={18} />
          <span className="grid h-14 w-14 place-items-center rounded-full text-ink shadow-[0_0_34px_rgba(255,90,31,0.8)] [background:var(--grad)]">
            <Mic size={22} />
          </span>
          <X size={19} />
        </div>
      </div>
    </div>
  );
}

function MeetSofia() {
  const { openChat } = useChat();
  return (
    <section className="shell py-16 sm:py-24">
      <div className="grid items-center gap-14 lg:grid-cols-2">
        <Reveal>
          <PhoneVoice />
        </Reveal>
        <Reveal delay={0.1}>
          <span className="eyebrow">Meet Sofía</span>
          <h2 className="h2 mt-4">
            See what your assistant <span className="serif grad-text text-[1.08em]">could feel like</span>
          </h2>
          <p className="lede mt-5">Sofía is our own assistant. Ask her about our services, how we work or how to book a demo. Tap the little robot any time, in English or Spanish.</p>
          <ul className="mt-7 space-y-3">
            {["Understands everyday questions", "Remembers what you were talking about", "Saves demo requests step by step"].map((item) => (
              <li key={item} className="flex items-center gap-3">
                <span className="grid h-6 w-6 place-items-center rounded-full text-ink [background:var(--grad)]">
                  <Check size={14} strokeWidth={3} />
                </span>
                {item}
              </li>
            ))}
          </ul>
          <button onClick={() => openChat("How does it work?")} className="btn btn-primary mt-8">
            Start a conversation <ArrowRight size={18} />
          </button>
        </Reveal>
      </div>
    </section>
  );
}

function ServicesPreview() {
  return (
    <section className="shell py-16 sm:py-24">
      <Reveal className="flex flex-col justify-between gap-5 sm:flex-row sm:items-end">
        <div className="max-w-2xl">
          <span className="eyebrow">Services</span>
          <h2 className="h2 mt-4">
            Everything it takes to <span className="serif grad-text text-[1.08em]">make AI useful</span>
          </h2>
        </div>
        <a href="#/services" className="btn btn-ghost w-fit shrink-0">
          All services <ArrowUpRight size={17} />
        </a>
      </Reveal>
      <div className="mt-12 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {SERVICES.map((service, index) => (
          <Reveal key={service.title} delay={(index % 3) * 0.07}>
            <Card className="h-full p-7 hover:-translate-y-1">
              <span className="grid h-12 w-12 place-items-center rounded-2xl text-ink [background:var(--grad)]">
                <service.icon size={22} />
              </span>
              <h3 className="mt-6 text-xl font-semibold tracking-tight">{service.title}</h3>
              <p className="mt-2 leading-relaxed text-mute">{service.summary}</p>
            </Card>
          </Reveal>
        ))}
      </div>
    </section>
  );
}

function ReviewsPreview() {
  return (
    <section className="shell py-16 sm:py-24">
      <Reveal className="mx-auto max-w-3xl text-center">
        <span className="eyebrow">Reviews</span>
        <h2 className="h2 mt-4">
          The kind of <span className="serif grad-text text-[1.08em]">everyday change</span> we aim for
        </h2>
      </Reveal>
      <div className="mt-12 grid gap-4 md:grid-cols-3">
        {REVIEWS.slice(0, 3).map((review, index) => (
          <Reveal key={review.name} delay={index * 0.08}>
            <Card className="flex h-full flex-col p-7">
              <p className="serif text-5xl leading-none text-ember" aria-hidden="true">“</p>
              <p className="mt-2 flex-1 text-lg leading-relaxed">{review.quote}</p>
              <p className="mt-6 text-sm font-semibold">{review.name}</p>
              <p className="text-sm text-mute">{review.role}</p>
            </Card>
          </Reveal>
        ))}
      </div>
      <Reveal className="mx-auto mt-6 max-w-xl">
        <PrototypeNote>These reviews are illustrative examples for this academic prototype, not statements from real customers.</PrototypeNote>
      </Reveal>
    </section>
  );
}

function Faq() {
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="shell py-16 sm:py-24">
      <div className="grid gap-10 lg:grid-cols-[1fr_1.5fr]">
        <Reveal>
          <span className="eyebrow">Questions</span>
          <h2 className="h2 mt-4">Good to know</h2>
        </Reveal>
        <Reveal delay={0.08}>
          <div className="border-t border-line">
            {FAQS.map((faq, index) => {
              const isOpen = open === index;
              return (
                <div key={faq.q} className="border-b border-line">
                  <button onClick={() => setOpen(isOpen ? null : index)} aria-expanded={isOpen} className="flex min-h-16 w-full items-center justify-between gap-4 py-5 text-left text-lg font-medium">
                    {faq.q}
                    <motion.span animate={{ rotate: isOpen ? 45 : 0 }} className="shrink-0 text-ember">
                      <Plus size={22} />
                    </motion.span>
                  </button>
                  <motion.div initial={false} animate={{ height: isOpen ? "auto" : 0, opacity: isOpen ? 1 : 0 }} className="overflow-hidden">
                    <p className="pb-6 leading-relaxed text-mute">{faq.a}</p>
                  </motion.div>
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}

export function CallToAction() {
  return (
    <section className="shell py-10">
      <Reveal>
        <div className="relative overflow-hidden rounded-[2.2rem] px-6 py-16 text-center sm:px-12 sm:py-24 [background:linear-gradient(120deg,#c5112f_0%,#ff4d18_55%,#ffa43c_100%)]">
          <div className="absolute -top-40 left-1/2 h-96 w-96 -translate-x-1/2 rounded-full bg-white/20 blur-3xl" />
          <div className="relative">
            <h2 className="h2 mx-auto max-w-3xl text-[#190904]">
              Let's find the first thing <span className="serif text-[1.08em]">AI should take off your plate</span>
            </h2>
            <a href="#/contact" className="btn mt-8 bg-[#120805] text-cream hover:bg-black">
              Book a demo <ArrowUpRight size={18} />
            </a>
          </div>
        </div>
      </Reveal>
    </section>
  );
}

export function Home() {
  return (
    <>
      <Hero />
      <Value />
      <Process />
      <MeetSofia />
      <ServicesPreview />
      <ReviewsPreview />
      <Faq />
      <CallToAction />
    </>
  );
}
