import { AnimatePresence, motion } from "motion/react";
import { Star } from "lucide-react";
import { useState } from "react";

import { Card, PageHero, PrototypeNote } from "../components/ui";
import { REVIEWS, type Review } from "../content/site";
import { CallToAction } from "./Home";

const FILTERS: ("All" | Review["industry"])[] = ["All", "Health", "Beauty", "Food", "Retail", "Services"];
const initials = (name: string) => name.split(" ").map((part) => part[0]).join("");

export function Reviews() {
  const [filter, setFilter] = useState<(typeof FILTERS)[number]>("All");
  const visible = REVIEWS.filter((review) => filter === "All" || review.industry === filter);
  return (
    <>
      <PageHero
        eyebrow="Reviews"
        title={
          <>
            Less busywork, <span className="serif grad-text text-[1.1em]">more time for customers</span>
          </>
        }
        lede="A look at the kind of results small businesses want from working with us."
      >
        <div className="mt-6 max-w-2xl">
          <PrototypeNote>All reviews on this page are illustrative examples written for this academic prototype. The people and businesses are fictional.</PrototypeNote>
        </div>
      </PageHero>
      <section className="shell">
        <div className="flex flex-wrap gap-2" role="group" aria-label="Filter reviews by industry">
          {FILTERS.map((item) => (
            <button
              key={item}
              onClick={() => setFilter(item)}
              aria-pressed={filter === item}
              className={`min-h-11 rounded-full px-4.5 py-2 text-sm font-medium transition ${filter === item ? "text-ink [background:var(--grad)]" : "border border-line text-mute hover:text-cream"}`}
            >
              {item}
            </button>
          ))}
        </div>
        <motion.div layout className="mt-8 grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
          <AnimatePresence mode="popLayout">
            {visible.map((review) => (
              <motion.div key={review.name} layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.3 }}>
                <Card className="flex h-full flex-col p-7">
                  <div className="flex gap-0.5 text-glow" role="img" aria-label="Illustrative example">
                    {[0, 1, 2, 3, 4].map((star) => (
                      <Star key={star} size={15} fill="currentColor" strokeWidth={0} />
                    ))}
                  </div>
                  <p className="mt-4 flex-1 text-[1.05rem] leading-relaxed">“{review.quote}”</p>
                  <div className="mt-6 flex items-center gap-3">
                    <span className="grid h-11 w-11 shrink-0 place-items-center rounded-full text-sm font-bold text-ink [background:var(--grad)]" aria-hidden="true">
                      {initials(review.name)}
                    </span>
                    <span>
                      <span className="block text-sm font-semibold">{review.name}</span>
                      <span className="block text-sm text-mute">{review.role}</span>
                    </span>
                  </div>
                </Card>
              </motion.div>
            ))}
          </AnimatePresence>
        </motion.div>
      </section>
      <div className="mt-16">
        <CallToAction />
      </div>
    </>
  );
}
