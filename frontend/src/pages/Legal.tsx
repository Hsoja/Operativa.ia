import { useState, type ReactNode } from "react";

import { PageHero, PrototypeNote } from "../components/ui";
import { clearLeads, getLeads } from "../lib/leads";

const UPDATED = "November 2, 2026";

function LegalPage({ eyebrow, title, intro, children }: { eyebrow: string; title: string; intro: string; children: ReactNode }) {
  return (
    <>
      <PageHero eyebrow={eyebrow} title={title} lede={intro} />
      <section className="shell">
        <div className="mx-auto max-w-3xl">
          <p className="text-sm text-faint">Last updated: {UPDATED}</p>
          <div className="mt-4">
            <PrototypeNote>Operativa.ia is an academic prototype. This is a draft document and has not been reviewed by a lawyer.</PrototypeNote>
          </div>
          <div className="legal">{children}</div>
        </div>
      </section>
    </>
  );
}

export function Terms() {
  return (
    <LegalPage eyebrow="Legal" title="Terms & Conditions" intro="The rules for using this website and talking to Sofía.">
      <h2>1. Who we are</h2>
      <p>Operativa.ia ("we", "us") is a project that offers AI implementation services for small businesses. This website is an academic prototype of that service.</p>
      <h2>2. Using this website</h2>
      <p>By using this site you agree to these terms. You agree not to:</p>
      <ul>
        <li>Disrupt the site or try to access parts of it you aren't allowed to reach.</li>
        <li>Send automated, abusive or unlawful content through the chat or forms.</li>
        <li>Try to make the assistant reveal internal information or act against its rules.</li>
      </ul>
      <h2>3. Sofía, our virtual assistant</h2>
      <p>Sofía is software, not a person. Her answers are general information and may be incomplete or wrong. They are not professional, legal, medical or financial advice, and they aren't a binding offer. Please check anything important with us directly.</p>
      <h2>4. Services and quotes</h2>
      <p>Descriptions on this site are general. Any real engagement, including its scope, price and timeline, would be set out in a separate written agreement. Nothing here is a guarantee of specific results.</p>
      <h2>5. Reviews and examples</h2>
      <p>Reviews and examples on this site are illustrative and were written for this prototype. They don't describe real customers or results.</p>
      <h2>6. Intellectual property</h2>
      <p>The Operativa.ia name, logo, the Sofía character, and the site's design and text belong to their respective owners. You may not copy or reuse them without permission.</p>
      <h2>7. Liability</h2>
      <p>This prototype is provided "as is", with no guarantee that it will be available or free of errors. To the extent the law allows, we aren't liable for losses resulting from your use of the site or from relying on its content.</p>
      <h2>8. Changes</h2>
      <p>We may update these terms. The date at the top shows the latest version, which applies from the moment it's published.</p>
      <h2>9. Contact</h2>
      <p>
        Questions? Reach us through the <a href="#/contact" className="text-cream underline underline-offset-3">contact page</a>.
      </p>
    </LegalPage>
  );
}

function ClearData() {
  const [count, setCount] = useState(() => getLeads().length);
  const [message, setMessage] = useState("");
  return (
    <div className="glass mt-5 rounded-2xl p-5">
      <p className="!text-cream">
        Messages saved on this device: <strong>{count}</strong>
      </p>
      <button
        className="btn btn-ghost mt-3 !min-h-11 !py-2 !text-sm"
        disabled={count === 0}
        onClick={() => {
          const ok = clearLeads();
          if (ok) setCount(0);
          setMessage(ok ? "Your saved messages were deleted from this device." : "We couldn't access this browser's storage.");
        }}
      >
        Delete my saved messages
      </button>
      {message && (
        <p role="status" className="mt-2 text-sm">
          {message}
        </p>
      )}
    </div>
  );
}

export function Privacy() {
  return (
    <LegalPage eyebrow="Legal" title="Privacy Policy" intro="What information this site collects, why, and the choices you have.">
      <h2>1. What we collect</h2>
      <ul>
        <li><strong>Contact form:</strong> your name, email, business name (optional), topic and message.</li>
        <li><strong>Chat with Sofía:</strong> what you type, and your name, business, email and need if you request a demo.</li>
      </ul>
      <p>Please don't share passwords, payment details, health information or other sensitive data.</p>
      <h2>2. Where it's stored today</h2>
      <p>In this version of the prototype, contact and demo requests are saved only in your own browser's local storage. They aren't sent to our team or to a server. Chat conversations aren't saved and disappear when you close or reload the page.</p>
      <ClearData />
      <h2>3. Why we use it</h2>
      <p>To answer your request and prepare a demo if you ask for one. We don't sell your information or use it for advertising.</p>
      <h2>4. Future changes</h2>
      <p>When the prototype connects to its server and AI providers, requests may be stored on that server and chat messages may be processed by those providers. We'll update this policy before that happens, including who receives the data and how long it's kept.</p>
      <h2>5. Cookies and tracking</h2>
      <p>This site doesn't use advertising or analytics cookies. Fonts are served from the site itself, so no third-party font service sees your visit.</p>
      <h2>6. Your choices</h2>
      <p>You can delete requests saved on this device with the button above, or by clearing your browser's site data. Depending on where you live, you may also have rights to access, correct or delete personal data.</p>
      <h2>7. Children</h2>
      <p>This site is intended for business owners and teams. It isn't directed at children.</p>
      <h2>8. Contact</h2>
      <p>
        For privacy questions, use the <a href="#/contact" className="text-cream underline underline-offset-3">contact page</a>.
      </p>
    </LegalPage>
  );
}
