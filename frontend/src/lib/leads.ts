/**
 * Solicitudes de contacto y demo.
 * Se envían al backend (POST /api/v1/public/{slug}/contact), que valida todo de nuevo.
 * Nada se guarda en el almacenamiento del navegador.
 */

import { postJson } from "./api";

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

export type LeadSource = "contact-form" | "sofia";
export type LeadErrors = Partial<Record<keyof LeadInput, string>>;
export type SubmitResult = "sent" | "invalid" | "rate_limited" | "error";

const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;

/** Quita caracteres de control e invisibles, y conserva saltos de línea. */
export const cleanText = (value: string): string =>
  value
    .normalize("NFC")
    .replace(/[\p{Cc}\p{Cf}]/gu, (ch) => (ch === "\n" ? ch : ""))
    .trim();

export const isValidEmail = (value: string): boolean => value.length <= 254 && EMAIL.test(value);

/** Ayuda al usuario a corregir antes de enviar. La validación que cuenta es la del servidor. */
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

export async function submitLead(input: LeadInput, source: LeadSource): Promise<SubmitResult> {
  if (!input.consent) return "invalid";
  const result = await postJson<{ status: string }>("/contact", {
    name: cleanText(input.name),
    email: cleanText(input.email),
    business: cleanText(input.business),
    topic: input.topic,
    message: cleanText(input.message),
    source,
    consent: true,
  });
  if (result.ok) return "sent";
  if (result.reason === "invalid") return "invalid";
  if (result.reason === "rate_limited") return "rate_limited";
  return "error";
}
