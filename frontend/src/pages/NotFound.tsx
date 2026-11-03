import { ArrowLeft } from "lucide-react";

import { Robot } from "../components/Robot";

export function NotFound() {
  return (
    <section className="shell flex min-h-[85dvh] flex-col items-center justify-center pt-28 text-center">
      <Robot mood="thinking" className="h-64 w-auto" />
      <h1 className="h2 mt-6">
        This page <span className="serif grad-text text-[1.08em]">got lost</span>
      </h1>
      <p className="lede mt-3">Sofía looked everywhere, but it isn't here.</p>
      <a href="#/" className="btn btn-primary mt-7">
        <ArrowLeft size={18} /> Back home
      </a>
    </section>
  );
}
