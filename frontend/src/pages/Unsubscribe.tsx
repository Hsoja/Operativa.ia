import { MailX } from "lucide-react";
import { useState } from "react";

import { Card, PageHero } from "../components/ui";
import { postJson } from "../lib/api";
import { unsubscribeTarget } from "../lib/router";

/**
 * Baja de correos (CASL). Hace falta un clic en el botón: abrir el enlace (GET) no cambia nada,
 * así los escáneres de enlaces de los correos no dan de baja a nadie por accidente.
 */
export function Unsubscribe() {
  const target = unsubscribeTarget(window.location.hash);
  const [state, setState] = useState<"idle" | "sending" | "done" | "error">("idle");

  const confirm = async () => {
    if (!target || state === "sending") return;
    setState("sending");
    const result = await postJson<{ status: string }>(`/unsubscribe/${target.token}`, {}, target.slug);
    setState(result.ok ? "done" : "error");
  };

  return (
    <>
      <PageHero eyebrow="Email preferences" title="Unsubscribe" />
      <section className="shell mx-auto max-w-xl">
        <Card className="p-8 text-center">
          <MailX size={36} className="mx-auto text-ember" aria-hidden="true" />
          {state === "done" ? (
            <p role="status" className="mt-4 text-lg">You've been unsubscribed. You won't receive more reminders or offers from this business.</p>
          ) : (
            <>
              <p className="mt-4 leading-relaxed text-mute">Stop receiving reminders and offers by email from this business.</p>
              <button className="btn btn-primary mt-6" onClick={() => void confirm()} disabled={!target || state === "sending"}>
                {state === "sending" ? "Unsubscribing…" : "Unsubscribe"}
              </button>
              {state === "error" && (
                <p role="alert" className="mt-4 text-sm">
                  We couldn't process this link. It may be invalid; please contact the business directly.
                </p>
              )}
              {!target && <p role="alert" className="mt-4 text-sm">This unsubscribe link isn't valid.</p>}
            </>
          )}
        </Card>
      </section>
    </>
  );
}
