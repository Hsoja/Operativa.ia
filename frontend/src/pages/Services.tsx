import { Check } from "lucide-react";

import { Card, PageHero, Reveal } from "../components/ui";
import { SERVICES, STEPS } from "../content/site";
import { CallToAction } from "./Home";

export function Services() {
  return (
    <>
      <PageHero
        eyebrow="Services"
        title={
          <>
            One partner, from <span className="serif grad-text text-[1.1em]">idea to everyday use</span>
          </>
        }
        lede="Pick what you need or let us handle the whole journey. Every project starts by understanding your business."
      />
      <section className="shell">
        <div className="grid gap-4 md:grid-cols-2">
          {SERVICES.map((service, index) => (
            <Reveal key={service.title} delay={(index % 2) * 0.08}>
              <Card className="h-full p-7 sm:p-9">
                <div className="flex items-start justify-between">
                  <span className="grid h-13 w-13 place-items-center rounded-2xl text-ink [background:var(--grad)]">
                    <service.icon size={24} />
                  </span>
                  <span className="serif text-3xl text-faint">0{index + 1}</span>
                </div>
                <h2 className="mt-6 text-2xl font-semibold tracking-tight">{service.title}</h2>
                <p className="mt-2 leading-relaxed text-mute">{service.summary}</p>
                <ul className="mt-6 space-y-2.5 border-t border-line pt-5">
                  {service.includes.map((item) => (
                    <li key={item} className="flex gap-2.5 text-[0.95rem]">
                      <Check size={18} className="mt-0.5 shrink-0 text-ember" />
                      {item}
                    </li>
                  ))}
                </ul>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>
      <section className="shell py-24">
        <Reveal className="max-w-2xl">
          <span className="eyebrow">How we work</span>
          <h2 className="h2 mt-4">A clear path, with no surprises</h2>
        </Reveal>
        <ol className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {STEPS.map((step, index) => (
            <Reveal key={step.title} delay={index * 0.07}>
              <li className="glass h-full list-none rounded-3xl p-6">
                <span className="serif grad-text text-4xl">{index + 1}</span>
                <h3 className="mt-3 text-lg font-semibold">{step.title}</h3>
                <p className="mt-2 text-[0.95rem] leading-relaxed text-mute">{step.text}</p>
              </li>
            </Reveal>
          ))}
        </ol>
        <Reveal className="mt-10">
          <Card className="p-7 sm:p-9">
            <h2 className="text-2xl font-semibold tracking-tight">What about pricing?</h2>
            <p className="mt-2 max-w-2xl leading-relaxed text-mute">Each business is different, so there's no one-size price. After a short discovery call, you get a written scope and a quote before committing to anything.</p>
          </Card>
        </Reveal>
      </section>
      <CallToAction />
    </>
  );
}
