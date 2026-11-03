import { motion } from "motion/react";
import { Info } from "lucide-react";
import type { CSSProperties, PointerEvent, ReactNode } from "react";

export function Reveal({ children, delay = 0, className = "" }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={{ opacity: 0, y: 26 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-60px" }}
      transition={{ duration: 0.7, delay, ease: [0.2, 0.7, 0.2, 1] }}
    >
      {children}
    </motion.div>
  );
}

/** Tarjeta con un brillo que sigue al cursor. */
export function Card({ children, className = "", style }: { children: ReactNode; className?: string; style?: CSSProperties }) {
  const onMove = (event: PointerEvent<HTMLDivElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    event.currentTarget.style.setProperty("--mx", `${event.clientX - box.left}px`);
    event.currentTarget.style.setProperty("--my", `${event.clientY - box.top}px`);
  };
  return (
    <div className={`card ${className}`} style={style} onPointerMove={onMove}>
      <div className="relative h-full">{children}</div>
    </div>
  );
}

export function PageHero({ eyebrow, title, lede, children }: { eyebrow: string; title: ReactNode; lede?: string; children?: ReactNode }) {
  return (
    <section className="shell pt-34 pb-14 sm:pt-44 sm:pb-20">
      <motion.div initial={{ opacity: 0, y: 24 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.8, ease: [0.2, 0.7, 0.2, 1] }} className="max-w-4xl">
        <span className="eyebrow">{eyebrow}</span>
        <h1 className="display mt-5">{title}</h1>
        {lede && <p className="lede mt-6 max-w-2xl">{lede}</p>}
        {children}
      </motion.div>
    </section>
  );
}

export function PrototypeNote({ children }: { children: ReactNode }) {
  return (
    <p className="flex items-start gap-2.5 rounded-2xl border border-glow/25 bg-glow/6 px-4 py-3 text-sm leading-relaxed text-mute">
      <Info size={17} className="mt-0.5 shrink-0 text-glow" aria-hidden="true" />
      <span>{children}</span>
    </p>
  );
}

export function Waveform({ bars = 26, className = "" }: { bars?: number; className?: string }) {
  return (
    <span className={`wave flex h-8 items-center gap-[3px] ${className}`} aria-hidden="true">
      {Array.from({ length: bars }, (_, i) => (
        <i key={i} style={{ height: `${28 + ((i * 37) % 72)}%`, animationDelay: `${(i * 0.09) % 1.1}s` }} />
      ))}
    </span>
  );
}
