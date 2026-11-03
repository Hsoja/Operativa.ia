/**
 * Solicitudes de contacto y demo.
 * Por ahora se guardan solo en este navegador. Al conectar la API, cambia saveLead por un POST.
 */

export const TOPICS = ["Book a demo", "Services question", "Partnership", "Something else"] as const;
export type Topic = (typeof TOPICS)[number];

export interface LeadInput {
  name: string;
  email: string;
  business: string;
  topic: string;
  message: string;
  consent: boolean;
}

export interface Lead extends Omit<LeadInput, "consent"> {
  id: string;
  source: "contact-form" | "sofia";
  createdAt: string;
}

export type LeadErrors = Partial<Record<keyof LeadInput, string>>;

const LEADS_BUCKET = "operativa.leads.v1";
const MAX_STORED = 50;
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Quita caracteres de control e invisibles, y conserva saltos de línea. */
export const cleanText = (value: string): string =>
  value
    .normalize("NFC")
    .replace(/[\p{Cc}\p{Cf}]/gu, (ch) => (ch === "\n" ? ch : ""))
    .trim();

export const isValidEmail = (value: string): boolean => value.length <= 254 && EMAIL.test(value);

export function validateLead(input: LeadInput): LeadErrors {
  const errors: LeadErrors = {};
  const name = cleanText(input.name);
  const message = cleanText(input.message);
  if (name.length < 2 || name.length > 80) errors.name = "Please enter your name.";
  if (!isValidEmail(cleanText(input.email))) errors.email = "Please enter a valid email address.";
  if (cleanText(input.business).length > 120) errors.business = "Please keep this under 120 characters.";
  if (!TOPICS.includes(input.topic as Topic)) errors.topic = "Please choose a topic.";
  if (message.length < 10) errors.message = "Tell us a little more (at least 10 characters).";
  if (message.length > 2000) errors.message = "Please keep your message under 2,000 characters.";
  if (!input.consent) errors.consent = "Please accept the Privacy Policy to continue.";
  return errors;
}

function readAll(): Lead[] {
  const raw = localStorage.getItem(LEADS_BUCKET);
  if (!raw) return [];
  const parsed: unknown = JSON.parse(raw);
  return Array.isArray(parsed) ? (parsed as Lead[]) : [];
}

export function getLeads(): Lead[] {
  try {
    return readAll();
  } catch {
    return [];
  }
}

export function saveLead(input: Omit<LeadInput, "consent">, source: Lead["source"]): boolean {
  const lead: Lead = {
    id: crypto.randomUUID(),
    source,
    createdAt: new Date().toISOString(),
    name: cleanText(input.name),
    email: cleanText(input.email),
    business: cleanText(input.business),
    topic: input.topic,
    message: cleanText(input.message),
  };
  try {
    let existing: Lead[] = [];
    try {
      existing = readAll();
    } catch {
      existing = [];
    }
    localStorage.setItem(LEADS_BUCKET, JSON.stringify([lead, ...existing].slice(0, MAX_STORED)));
    return true;
  } catch {
    return false;
  }
}

export function clearLeads(): boolean {
  try {
    localStorage.removeItem(LEADS_BUCKET);
    return true;
  } catch {
    return false;
  }
}
