import { Bot, CalendarClock, GraduationCap, Headphones, Plug, Search, type LucideIcon } from "lucide-react";

export interface Service {
  icon: LucideIcon;
  title: string;
  summary: string;
  includes: string[];
}

export const SERVICES: Service[] = [
  {
    icon: Search,
    title: "Business discovery",
    summary: "We learn how your business really runs before we suggest anything.",
    includes: ["Review of daily tasks and customer conversations", "Clear list of what to automate first", "Written plan and scope"],
  },
  {
    icon: Bot,
    title: "Custom AI assistant",
    summary: "An assistant that knows your services, your policies and your tone.",
    includes: ["Trained on your real information", "Answers in your brand's voice", "Hands complex cases to a person"],
  },
  {
    icon: Plug,
    title: "Tool integrations",
    summary: "It works with the tools you already use, so nobody starts from zero.",
    includes: ["Calendars, email and messaging", "Spreadsheets and CRMs", "Access limited to what's needed"],
  },
  {
    icon: CalendarClock,
    title: "Process automation",
    summary: "Repetitive work like scheduling and follow-ups runs on its own.",
    includes: ["Appointments and reminders", "Request capture and routing", "Follow-ups your team can review"],
  },
  {
    icon: GraduationCap,
    title: "Team training",
    summary: "Your people learn to work with the assistant and stay in control.",
    includes: ["Hands-on sessions for your team", "Simple guides for everyday use", "Clear rules for when a person steps in"],
  },
  {
    icon: Headphones,
    title: "Ongoing support",
    summary: "We keep tuning it as your business changes.",
    includes: ["Reviews of real conversations", "Updates to services and policies", "One point of contact for help"],
  },
];

export const STEPS = [
  { title: "Understand", text: "We map how your business works, who does what and where time gets lost." },
  { title: "Customize", text: "We shape the assistant around your information, your rules and your tone." },
  { title: "Connect", text: "We link it to your calendar, inbox and the other tools you already use." },
  { title: "Support", text: "We train your team, watch how it performs and keep making it better." },
];

export interface Review {
  quote: string;
  name: string;
  role: string;
  industry: "Health" | "Beauty" | "Food" | "Retail" | "Services";
}

export const REVIEWS: Review[] = [
  { quote: "They spent time understanding how our front desk works before building anything. It felt made for us.", name: "Elena R.", role: "Dental clinic owner", industry: "Health" },
  { quote: "Our clients get answers at night, and in the morning we only see the requests that need us.", name: "Marco D.", role: "Hair salon manager", industry: "Beauty" },
  { quote: "We kept our tools. The assistant simply fit in around them, which is what convinced my team.", name: "Priya S.", role: "Physiotherapy practice", industry: "Health" },
  { quote: "Reservation questions used to interrupt the kitchen all day. Now they rarely reach us.", name: "Tomás G.", role: "Restaurant owner", industry: "Food" },
  { quote: "What I valued most was the training. Everyone knows when the assistant answers and when they should step in.", name: "Hannah L.", role: "Accounting office", industry: "Services" },
  { quote: "It answers like we do. Customers notice the tone is ours and not some generic robot.", name: "Diego M.", role: "Neighborhood bike shop", industry: "Retail" },
  { quote: "Follow-ups were always the first thing we dropped. Having them prepared for us changed our week.", name: "Sara K.", role: "Veterinary clinic", industry: "Health" },
  { quote: "No big speech about AI. They looked at our day, found the slow parts and started there.", name: "Luis P.", role: "Home repair services", industry: "Services" },
  { quote: "They came back after launch and adjusted things when our menu and hours changed.", name: "Amara O.", role: "Café owner", industry: "Food" },
];

export const FAQS = [
  { q: "Is this just another chatbot?", a: "No. The assistant is only one part. Our work is the implementation: understanding your business, customizing the assistant, connecting your tools and supporting your team." },
  { q: "Do I need technical knowledge?", a: "No. We handle the setup and train your team to use it day to day." },
  { q: "Do I have to change my tools?", a: "Usually not. We start from what you already use and confirm each integration during discovery." },
  { q: "How much does it cost?", a: "It depends on the scope. We share a quote after a short discovery call, once we know which processes and tools are involved." },
];
