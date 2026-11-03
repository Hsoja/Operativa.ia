import { useId } from "react";

export function LogoMark({ className = "h-8 w-8" }: { className?: string }) {
  const id = useId().replace(/:/g, "");
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden="true">
      <defs>
        <linearGradient id={id} x1="8" y1="58" x2="56" y2="6" gradientUnits="userSpaceOnUse">
          <stop offset="0" stopColor="#E5173F" />
          <stop offset=".55" stopColor="#FF5A1F" />
          <stop offset="1" stopColor="#FFB347" />
        </linearGradient>
      </defs>
      <path d="M38 9.8A23 23 0 1 0 54.3 26" fill="none" stroke={`url(#${id})`} strokeWidth="9" strokeLinecap="round" />
      <circle cx="48.3" cy="15.7" r="5" fill="#FFB347" />
      <rect x="21" y="25" width="6.5" height="14" rx="3.25" fill={`url(#${id})`} />
      <rect x="35.5" y="25" width="6.5" height="14" rx="3.25" fill={`url(#${id})`} />
    </svg>
  );
}

export function Logo() {
  return (
    <span className="inline-flex items-center gap-2.5">
      <LogoMark />
      <span className="text-[1.15rem] font-bold tracking-[-0.03em]">
        Operativa<span className="grad-text">.ia</span>
      </span>
    </span>
  );
}
