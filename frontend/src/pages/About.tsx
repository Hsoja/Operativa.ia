import { Compass, HeartHandshake, ShieldCheck, Users } from "lucide-react";

import { ParticleOrb } from "../components/ParticleOrb";
import { Robot } from "../components/Robot";
import { Card, PageHero, PrototypeNote, Reveal } from "../components/ui";
import { CallToAction } from "./Home";

const VALUES = [
  { icon: Compass, title: "Business first", text: "We start with your problems and only then choose the technology." },
  { icon: Users, title: "People in control", text: "AI should free your team's time, not replace their judgment." },
  { icon: ShieldCheck, title: "Careful with data", text: "We ask only for the access we need, and we explain why we need it." },
  { icon: HeartHandshake, title: "Here for the long run", text: "A launch is the beginning. We keep adjusting with you." },
];

export function About() {
  return (
    <>
      <PageHero
        eyebrow="About us"
        title={
          <>
            Small businesses deserve <span className="serif grad-text text-[1.1em]">AI that truly helps</span>
          </>
        }
        lede="Big companies have whole teams to make AI work. Small businesses have a busy owner and too little time. Operativa.ia exists to close that gap."
      />
      <section className="shell">
        <div className="grid items-center gap-10 lg:grid-cols-2">
          <Reveal>
            <div className="relative mx-auto aspect-square w-full max-w-lg">
              <ParticleOrb className="absolute inset-0 h-full w-full" />
              <div className="absolute inset-0 grid place-items-center">
                <Robot mood="happy" className="h-[68%] w-auto" />
              </div>
            </div>
          </Reveal>
          <Reveal delay={0.1}>
            <h2 className="h2">Our story</h2>
            <div className="lede mt-5 space-y-4">
              <p>We kept seeing the same pattern: a business buys an AI tool, nobody has time to set it up, and it never quite fits how the team works.</p>
              <p>So we made the implementation our product. We sit down with you, learn your routine and build the assistant around it. Then we stay to make sure it keeps working.</p>
            </div>
            <div className="mt-6">
              <PrototypeNote>Operativa.ia is an academic project. This site is a working prototype of the service.</PrototypeNote>
            </div>
          </Reveal>
        </div>
      </section>
      <section className="shell py-24">
        <Reveal className="max-w-2xl">
          <span className="eyebrow">What guides us</span>
          <h2 className="h2 mt-4">
            Four things we <span className="serif grad-text text-[1.08em]">won't compromise on</span>
          </h2>
        </Reveal>
        <div className="mt-10 grid gap-4 sm:grid-cols-2">
          {VALUES.map((value, index) => (
            <Reveal key={value.title} delay={(index % 2) * 0.08}>
              <Card className="h-full p-7">
                <value.icon size={26} className="text-ember" />
                <h3 className="mt-5 text-xl font-semibold tracking-tight">{value.title}</h3>
                <p className="mt-2 leading-relaxed text-mute">{value.text}</p>
              </Card>
            </Reveal>
          ))}
        </div>
      </section>
      <CallToAction />
    </>
  );
}
