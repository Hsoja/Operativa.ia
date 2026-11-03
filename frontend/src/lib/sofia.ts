/**
 * Motor local de Sofía: entiende intenciones, recuerda el tema y guía la solicitud de demo.
 * No llama a ningún modelo. Al conectar la API, reemplaza respondLocally dentro de askSofia.
 * Sofía nunca da precios: dependen del alcance y se confirman en una llamada.
 */

import { cleanText, isValidEmail, saveLead } from "./leads";

export type Lang = "en" | "es";
type Text = Record<Lang, string>;

interface Intent {
  id: string;
  keywords: string[];
  answer: Text;
  more?: Text;
  suggestions: Text[];
}

type BookingStep = "name" | "business" | "email" | "need";

export interface ChatState {
  lastIntent: string | null;
  lang: Lang;
  booking: { step: BookingStep; name: string; business: string; email: string } | null;
}

export interface Reply {
  text: string;
  suggestions: string[];
  state: ChatState;
}

export const initialState: ChatState = { lastIntent: null, lang: "en", booking: null };

const S = {
  demo: { en: "Book a demo", es: "Agendar una demo" },
  how: { en: "How does it work?", es: "¿Cómo funciona?" },
  services: { en: "What do you offer?", es: "¿Qué ofrecen?" },
  price: { en: "How much does it cost?", es: "¿Cuánto cuesta?" },
  tools: { en: "Which tools connect?", es: "¿Qué herramientas conectan?" },
  security: { en: "Is my data safe?", es: "¿Mis datos están seguros?" },
  more: { en: "Tell me more", es: "Cuéntame más" },
  time: { en: "How long does it take?", es: "¿Cuánto tarda?" },
} satisfies Record<string, Text>;

const INTENTS: Intent[] = [
  {
    id: "greeting",
    keywords: ["hi", "hello", "hey", "hola", "buenas", "buenos", "saludos", "good morning"],
    answer: {
      en: "Hi! I'm Sofía, Operativa.ia's assistant. What does your business do, and what takes up most of your team's time?",
      es: "¡Hola! Soy Sofía, la asistente de Operativa.ia. ¿A qué se dedica tu negocio y qué le quita más tiempo a tu equipo?",
    },
    suggestions: [S.services, S.how, S.demo],
  },
  {
    id: "about",
    keywords: ["what is operativa", "who are you", "what do you do", "about", "company", "quienes son", "que es operativa", "que hacen", "a que se dedican", "empresa", "operativa"],
    answer: {
      en: "Operativa.ia implements AI for small businesses. We learn how you work, customize an assistant to fit, connect it to your tools and support your team. The chatbot is only one part: the implementation is the real value.",
      es: "Operativa.ia implementa IA para pequeños negocios. Entendemos cómo trabajas, adaptamos un asistente a tu operación, lo conectamos con tus herramientas y acompañamos a tu equipo. El chatbot es solo una parte: el valor real está en la implementación.",
    },
    more: {
      en: "Our idea is simple: AI should fit your business, not the other way around. You keep your way of working, and the technology adapts to it.",
      es: "Nuestra idea es simple: la IA debe adaptarse a tu negocio, no al revés. Conservas tu forma de trabajar y la tecnología se ajusta a ella.",
    },
    suggestions: [S.services, S.how, S.demo],
  },
  {
    id: "services",
    keywords: ["service", "services", "offer", "provide", "servicio", "servicios", "ofrecen", "ofreces", "solutions", "soluciones", "chatbot", "asistente", "automate", "automation", "automatizar", "automatizacion"],
    answer: {
      en: "We offer six services: business discovery, a custom AI assistant, tool integrations, process automation, team training and ongoing support. Which one sounds closest to what you need?",
      es: "Ofrecemos seis servicios: diagnóstico del negocio, asistente de IA a medida, integración de herramientas, automatización de procesos, capacitación del equipo y soporte continuo. ¿Cuál se acerca más a lo que necesitas?",
    },
    more: {
      en: "A typical first project is an assistant that answers common questions, captures requests and hands the tricky ones to your team. You can see the details on the Services page.",
      es: "Un primer proyecto típico es un asistente que responde preguntas frecuentes, recoge solicitudes y pasa los casos difíciles a tu equipo. Tienes los detalles en la página de Servicios.",
    },
    suggestions: [S.how, S.price, S.demo],
  },
  {
    id: "process",
    keywords: ["how does it work", "how it works", "process", "steps", "start", "implementation", "implement", "como funciona", "proceso", "pasos", "empezar", "implementacion", "implementan", "funciona"],
    answer: {
      en: "It takes four steps: 1) Understand: we map how your business works. 2) Customize: we train the assistant on your information and tone. 3) Connect: we link it to the tools you already use. 4) Support: we train your team and keep improving it.",
      es: "Son cuatro pasos: 1) Entender: mapeamos cómo funciona tu negocio. 2) Adaptar: entrenamos al asistente con tu información y tu tono. 3) Conectar: lo enlazamos con las herramientas que ya usas. 4) Acompañar: capacitamos a tu equipo y lo seguimos mejorando.",
    },
    more: {
      en: "The first step is the most important one. We look at real conversations and tasks before building anything, so the assistant solves a problem you truly have.",
      es: "El primer paso es el más importante. Revisamos conversaciones y tareas reales antes de construir nada, para que el asistente resuelva un problema que de verdad tienes.",
    },
    suggestions: [S.time, S.tools, S.demo],
  },
  {
    id: "pricing",
    keywords: ["price", "prices", "pricing", "cost", "costs", "how much", "plan", "plans", "fee", "budget", "precio", "precios", "cuesta", "cuanto", "costo", "costos", "tarifa", "planes", "presupuesto", "cobran"],
    answer: {
      en: "I can't quote a price here because it depends on the scope: how many processes, tools and people are involved. The team confirms a quote after a short discovery call. Would you like to request one?",
      es: "No puedo darte un precio por aquí porque depende del alcance: cuántos procesos, herramientas y personas participan. El equipo confirma la cotización después de una llamada breve. ¿Quieres solicitarla?",
    },
    suggestions: [S.demo, S.how],
  },
  {
    id: "timeline",
    keywords: ["how long", "timeline", "time", "when", "fast", "weeks", "cuanto tarda", "cuanto tiempo", "tiempo", "tarda", "demora", "rapido", "semanas"],
    answer: {
      en: "It depends on the scope. A focused assistant with few integrations moves faster than a project with several tools and teams. You get a timeline right after the discovery call, before committing to anything.",
      es: "Depende del alcance. Un asistente enfocado y con pocas integraciones avanza más rápido que un proyecto con varias herramientas y equipos. Recibes un calendario justo después de la llamada, antes de comprometerte.",
    },
    suggestions: [S.how, S.demo],
  },
  {
    id: "tools",
    keywords: ["tool", "tools", "integrate", "integration", "integrations", "connect", "calendar", "crm", "email", "whatsapp", "spreadsheet", "herramienta", "herramientas", "integrar", "integracion", "integraciones", "conectar", "conectan", "calendario", "correo", "hoja de calculo", "excel"],
    answer: {
      en: "We start with what you already use, like calendars, email, messaging, spreadsheets and CRMs. Each integration is confirmed during discovery, with access limited to what the assistant actually needs.",
      es: "Partimos de lo que ya usas, como calendarios, correo, mensajería, hojas de cálculo y CRM. Cada integración se confirma en el diagnóstico, con acceso limitado a lo que el asistente realmente necesita.",
    },
    suggestions: [S.security, S.demo],
  },
  {
    id: "security",
    keywords: ["security", "secure", "safe", "privacy", "data", "gdpr", "confidential", "seguridad", "seguro", "seguros", "privacidad", "datos", "confidencial"],
    answer: {
      en: "Your data matters to us. We give the assistant only the access it needs, keep credentials out of the browser and never ask for passwords in chat. Please don't share sensitive information here. You can read more in the Privacy Policy.",
      es: "Tus datos nos importan. Le damos al asistente solo el acceso que necesita, mantenemos las credenciales fuera del navegador y nunca pedimos contraseñas por chat. Por favor no compartas información sensible aquí. Puedes leer más en la Política de Privacidad.",
    },
    suggestions: [S.tools, S.demo],
  },
  {
    id: "industries",
    keywords: ["industry", "industries", "clinic", "restaurant", "salon", "store", "shop", "small business", "my business", "sector", "industria", "clinica", "restaurante", "tienda", "salon", "negocio", "pyme", "pymes", "consultorio"],
    answer: {
      en: "We focus on small service businesses, such as clinics, salons, restaurants, shops and professional offices. If customers ask you the same things every day or you lose time on scheduling, you're a good fit.",
      es: "Nos enfocamos en pequeños negocios de servicios, como clínicas, salones, restaurantes, tiendas y despachos. Si tus clientes preguntan lo mismo todos los días o pierdes tiempo agendando, encajas muy bien.",
    },
    suggestions: [S.services, S.demo],
  },
  {
    id: "support",
    keywords: ["support", "training", "train", "help my team", "maintenance", "soporte", "capacitacion", "capacitar", "mantenimiento", "acompanamiento", "equipo"],
    answer: {
      en: "We stay after launch. We train your team, review how the assistant is performing and adjust it as your business changes.",
      es: "Seguimos contigo después del lanzamiento. Capacitamos a tu equipo, revisamos cómo funciona el asistente y lo ajustamos cuando tu negocio cambia.",
    },
    suggestions: [S.how, S.demo],
  },
  {
    id: "sofia",
    keywords: ["are you a bot", "are you real", "are you human", "are you ai", "your name", "who is sofia", "sofia", "eres un bot", "eres real", "eres humana", "eres ia", "tu nombre", "quien eres", "robot"],
    answer: {
      en: "I'm Sofía, a virtual assistant, not a person. On this prototype I answer from Operativa.ia's built-in knowledge. If you need a person, I can pass your request to the team.",
      es: "Soy Sofía, una asistente virtual, no una persona. En este prototipo respondo con la información integrada de Operativa.ia. Si necesitas a una persona, puedo pasarle tu solicitud al equipo.",
    },
    suggestions: [S.demo, S.services],
  },
  {
    id: "thanks",
    keywords: ["thanks", "thank you", "great", "perfect", "awesome", "gracias", "perfecto", "excelente", "genial"],
    answer: {
      en: "You're welcome! Is there anything else you'd like to know?",
      es: "¡Con gusto! ¿Hay algo más que quieras saber?",
    },
    suggestions: [S.services, S.demo],
  },
  {
    id: "bye",
    keywords: ["bye", "goodbye", "see you", "adios", "hasta luego", "nos vemos"],
    answer: { en: "Thanks for stopping by. See you soon!", es: "Gracias por visitarnos. ¡Hasta pronto!" },
    suggestions: [S.demo],
  },
];

const BOOKING_WORDS = ["book", "demo", "schedule", "appointment", "contact", "talk to", "speak to", "human", "person", "call me", "quote", "agendar", "agenda", "cita", "contacto", "contactar", "hablar con", "persona", "humano", "llamada", "llamame", "cotizacion", "solicitar", "quiero una demo"];
const MORE_WORDS = ["tell me more", "more", "go on", "explain", "cuentame mas", "mas", "explica", "explicame", "sigue", "detalles", "details"];
const YES_WORDS = ["yes", "sure", "ok", "okay", "please", "si", "claro", "dale", "por favor", "va"];
const CANCEL_WORDS = ["cancel", "stop", "never mind", "nevermind", "cancelar", "cancela", "olvidalo", "dejalo", "ya no"];
const SPANISH = /[¿¡ñáéíóú]|\b(hola|que|como|cuanto|cuesta|quiero|necesito|tienen|negocio|gracias|precio|para|una|los|las|por|con|mi|buenas|servicios?|ayuda|donde|cuando|tarda|datos|soy)\b/i;
const ENGLISH = /\b(the|what|how|much|hello|hi|do|does|is|are|you|your|my|want|need|thanks|with)\b/i;

export const normalize = (value: string): string =>
  value
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[^a-z0-9@.\s]/g, " ")
    .replace(/\s+/g, " ")
    .trim();

/** Distancia de edición limitada: tolera erratas de una letra. */
function closeEnough(a: string, b: string): boolean {
  if (a === b) return true;
  if (Math.min(a.length, b.length) < 5 || Math.abs(a.length - b.length) > 1) return false;
  let i = 0;
  let j = 0;
  let edits = 0;
  while (i < a.length && j < b.length) {
    if (a[i] === b[j]) {
      i++;
      j++;
    } else {
      if (++edits > 1) return false;
      if (a.length > b.length) i++;
      else if (b.length > a.length) j++;
      else {
        i++;
        j++;
      }
    }
  }
  return edits + (a.length - i) + (b.length - j) <= 1;
}

function matches(text: string, words: string[], keyword: string): boolean {
  const key = normalize(keyword);
  if (key.includes(" ")) return ` ${text} `.includes(` ${key} `);
  return words.some((word) => closeEnough(word, key));
}

const hasAny = (text: string, list: string[]): boolean => {
  const words = text.split(" ");
  return list.some((keyword) => matches(text, words, keyword));
};

function detectLang(raw: string, previous: Lang): Lang {
  const es = SPANISH.test(raw);
  const en = ENGLISH.test(raw);
  if (es && !en) return "es";
  if (en && !es) return "en";
  return previous;
}

function bestIntent(text: string): Intent | null {
  const words = text.split(" ");
  let best: Intent | null = null;
  let bestScore = 0;
  for (const intent of INTENTS) {
    let score = 0;
    for (const keyword of intent.keywords) {
      // Las frases pesan más que las palabras sueltas: son mucho más específicas
      if (matches(text, words, keyword)) score += keyword.includes(" ") ? 3 : 1;
    }
    // Un saludo solo gana si no hay nada más concreto en el mensaje
    if (intent.id === "greeting" || intent.id === "thanks") score *= 0.5;
    if (score > bestScore) {
      best = intent;
      bestScore = score;
    }
  }
  return best;
}

const pick = (lang: Lang, items: Text[]): string[] => items.map((item) => item[lang]);

const FALLBACK: Text = {
  en: "I'm not sure about that one. I can help with services, how the process works, integrations, data safety or booking a demo. What would you like to know?",
  es: "No estoy segura de eso. Puedo ayudarte con servicios, cómo funciona el proceso, integraciones, seguridad de datos o agendar una demo. ¿Qué te gustaría saber?",
};

const BOOKING_PROMPTS: Record<BookingStep, Text> = {
  name: { en: "Happy to set that up. What's your name? (Say \"cancel\" any time.)", es: "Con gusto. ¿Cómo te llamas? (Di \"cancelar\" cuando quieras.)" },
  business: { en: "Nice to meet you, {name}. What's the name of your business?", es: "Mucho gusto, {name}. ¿Cómo se llama tu negocio?" },
  email: { en: "Which email should the team use to reach you?", es: "¿A qué correo te puede escribir el equipo?" },
  need: { en: "Last one: what would you like the assistant to help with?", es: "Última pregunta: ¿con qué te gustaría que te ayudara el asistente?" },
};

function continueBooking(raw: string, state: ChatState): Reply {
  const booking = state.booking!;
  const lang = state.lang;
  const text = cleanText(raw);
  const ask = (next: ChatState["booking"], prompt: Text, name = ""): Reply => ({
    text: prompt[lang].replace("{name}", name),
    suggestions: [],
    state: { ...state, booking: next },
  });

  if (hasAny(normalize(text), CANCEL_WORDS)) {
    return {
      text: lang === "es" ? "Sin problema, lo dejamos aquí. ¿Te ayudo con algo más?" : "No problem, we'll leave it there. Can I help with anything else?",
      suggestions: pick(lang, [S.services, S.how]),
      state: { ...state, booking: null },
    };
  }

  switch (booking.step) {
    case "name":
      if (text.length < 2 || text.length > 80) {
        return ask(booking, { en: "Could you tell me your name?", es: "¿Me dices tu nombre?" });
      }
      return ask({ ...booking, step: "business", name: text }, BOOKING_PROMPTS.business, text);
    case "business":
      return ask({ ...booking, step: "email", business: text.slice(0, 120) }, BOOKING_PROMPTS.email);
    case "email":
      if (!isValidEmail(text)) {
        return ask(booking, { en: "That doesn't look like an email. Could you check it? Example: name@business.com", es: "Ese correo no parece válido. ¿Lo revisas? Ejemplo: nombre@negocio.com" });
      }
      return ask({ ...booking, step: "need", email: text }, BOOKING_PROMPTS.need);
    case "need": {
      const saved = saveLead(
        { name: booking.name, business: booking.business, email: booking.email, topic: "Book a demo", message: text.slice(0, 2000) },
        "sofia",
      );
      const done: Text = saved
        ? {
            en: `Thanks, ${booking.name}! I saved your demo request. This prototype stores it on this device only, so nobody has been notified yet.`,
            es: `¡Gracias, ${booking.name}! Guardé tu solicitud de demo. Este prototipo la almacena solo en este dispositivo, así que todavía no se ha avisado a nadie.`,
          }
        : {
            en: "I couldn't save your request because this browser blocks local storage. Please try the contact form in another browser.",
            es: "No pude guardar tu solicitud porque este navegador bloquea el almacenamiento local. Prueba el formulario de contacto en otro navegador.",
          };
      return { text: done[lang], suggestions: pick(lang, [S.how, S.tools]), state: { ...state, booking: null, lastIntent: null } };
    }
  }
}

export function respondLocally(rawMessage: string, previous: ChatState): Reply {
  const raw = rawMessage.slice(0, 2000);
  const state: ChatState = previous.booking ? previous : { ...previous, lang: detectLang(raw, previous.lang) };

  if (state.booking) return continueBooking(raw, state);

  const text = normalize(raw);
  const lang = state.lang;
  const startBooking = (): Reply => ({
    text: BOOKING_PROMPTS.name[lang],
    suggestions: [],
    state: { ...state, booking: { step: "name", name: "", business: "", email: "" }, lastIntent: "booking" },
  });

  // Solo tras ofrecer cotización, un "sí" inicia la solicitud
  if (state.lastIntent === "pricing" && hasAny(text, YES_WORDS) && text.split(" ").length <= 3) return startBooking();

  if (text.split(" ").length <= 4 && hasAny(text, MORE_WORDS)) {
    const current = INTENTS.find((intent) => intent.id === state.lastIntent);
    if (current?.more) return { text: current.more[lang], suggestions: pick(lang, current.suggestions), state };
    if (current) return { text: current.answer[lang], suggestions: pick(lang, current.suggestions), state };
  }

  const intent = bestIntent(text);
  // Una pregunta de precio o de tiempo gana a "agendar cita" o "contacto" dentro de la misma frase
  if (hasAny(text, BOOKING_WORDS) && intent?.id !== "pricing" && intent?.id !== "timeline") return startBooking();

  if (intent) {
    return {
      text: intent.answer[lang],
      suggestions: pick(lang, intent.more ? [S.more, ...intent.suggestions].slice(0, 3) : intent.suggestions),
      state: { ...state, lastIntent: intent.id },
    };
  }
  return { text: FALLBACK[lang], suggestions: pick(lang, [S.services, S.how, S.demo]), state: { ...state, lastIntent: null } };
}

export const WELCOME: Reply = {
  text: "Hi, I'm Sofía! Ask me anything about Operativa.ia, in English or Spanish.",
  suggestions: [S.services.en, S.how.en, S.price.en, S.demo.en],
  state: initialState,
};

/** Punto único de conexión con la API futura. */
export async function askSofia(message: string, state: ChatState): Promise<Reply> {
  const reply = respondLocally(message, state);
  const pause = Math.min(1400, 450 + reply.text.length * 5);
  await new Promise((resolve) => setTimeout(resolve, pause));
  return reply;
}
