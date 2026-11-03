import { motion, useMotionValue, useReducedMotion, useSpring } from "motion/react";
import { useEffect, useId, useRef } from "react";

type Mood = "idle" | "thinking" | "happy";

/** Hace que los ojos sigan al cursor. */
function useEyeTracking(ref: React.RefObject<SVGSVGElement>, range: number) {
  const rawX = useMotionValue(0);
  const rawY = useMotionValue(0);
  const x = useSpring(rawX, { stiffness: 140, damping: 16 });
  const y = useSpring(rawY, { stiffness: 140, damping: 16 });
  const reduced = useReducedMotion();

  useEffect(() => {
    if (reduced) return;
    const onMove = (event: PointerEvent) => {
      const box = ref.current?.getBoundingClientRect();
      if (!box) return;
      const dx = event.clientX - (box.left + box.width / 2);
      const dy = event.clientY - (box.top + box.height * 0.3);
      const distance = Math.hypot(dx, dy) || 1;
      const pull = Math.min(1, distance / 320);
      rawX.set((dx / distance) * range * pull);
      rawY.set((dy / distance) * range * 0.7 * pull);
    };
    window.addEventListener("pointermove", onMove, { passive: true });
    return () => window.removeEventListener("pointermove", onMove);
  }, [range, rawX, rawY, reduced, ref]);

  return { x, y };
}

function Face({ cx, cy, mood, x, y, id }: { cx: number; cy: number; mood: Mood; x: unknown; y: unknown; id: string }) {
  return (
    <motion.g style={{ x, y } as never}>
      {[-27, 27].map((offset) => (
        <motion.rect
          key={offset}
          x={cx + offset - 10}
          y={cy - 15}
          width="20"
          height="30"
          rx="10"
          fill={`url(#${id}-eye)`}
          filter={`url(#${id}-glow)`}
          style={{ transformBox: "fill-box", transformOrigin: "center" }}
          animate={mood === "thinking" ? { scaleY: [1, 0.45, 1], scaleX: [1, 1.15, 1] } : { scaleY: [1, 1, 0.08, 1, 1, 0.08, 1] }}
          transition={
            mood === "thinking"
              ? { duration: 0.9, repeat: Infinity, ease: "easeInOut" }
              : { duration: 5.2, repeat: Infinity, times: [0, 0.46, 0.48, 0.5, 0.92, 0.94, 0.96] }
          }
        />
      ))}
      <path
        d={mood === "happy" ? `M${cx - 14} ${cy + 22} Q${cx} ${cy + 38} ${cx + 14} ${cy + 22}` : `M${cx - 9} ${cy + 25} Q${cx} ${cy + 33} ${cx + 9} ${cy + 25}`}
        fill="none"
        stroke={`url(#${id}-eye)`}
        strokeWidth="5"
        strokeLinecap="round"
        filter={`url(#${id}-glow)`}
      />
    </motion.g>
  );
}

function Defs({ id }: { id: string }) {
  return (
    <defs>
      <linearGradient id={`${id}-shell`} x1="0" y1="0" x2="1" y2="1">
        <stop offset="0" stopColor="#FFFFFF" />
        <stop offset=".55" stopColor="#F4E9E1" />
        <stop offset="1" stopColor="#BFA89B" />
      </linearGradient>
      <linearGradient id={`${id}-body`} x1="0" y1="0" x2=".8" y2="1">
        <stop offset="0" stopColor="#FFFDFB" />
        <stop offset=".6" stopColor="#EBDDD3" />
        <stop offset="1" stopColor="#A98F81" />
      </linearGradient>
      <linearGradient id={`${id}-visor`} x1="0" y1="0" x2="0" y2="1">
        <stop offset="0" stopColor="#2A1712" />
        <stop offset="1" stopColor="#090403" />
      </linearGradient>
      <linearGradient id={`${id}-eye`} x1="0" y1="1" x2="1" y2="0">
        <stop offset="0" stopColor="#FF4A2B" />
        <stop offset="1" stopColor="#FFC15E" />
      </linearGradient>
      <filter id={`${id}-glow`} x="-80%" y="-80%" width="260%" height="260%">
        <feGaussianBlur stdDeviation="3.2" result="blur" />
        <feMerge>
          <feMergeNode in="blur" />
          <feMergeNode in="blur" />
          <feMergeNode in="SourceGraphic" />
        </feMerge>
      </filter>
    </defs>
  );
}

function Head({ id, mood, x, y }: { id: string; mood: Mood; x: unknown; y: unknown }) {
  return (
    <g>
      <line x1="160" y1="42" x2="160" y2="20" stroke="#D8C7BC" strokeWidth="6" strokeLinecap="round" />
      <motion.circle
        cx="160"
        cy="15"
        r="9"
        fill={`url(#${id}-eye)`}
        filter={`url(#${id}-glow)`}
        animate={{ opacity: [1, 0.45, 1] }}
        transition={{ duration: 1.8, repeat: Infinity }}
      />
      <rect x="62" y="82" width="24" height="56" rx="12" fill="#CDB9AD" />
      <rect x="234" y="82" width="24" height="56" rx="12" fill="#A98F81" />
      <rect x="74" y="38" width="172" height="142" rx="58" fill={`url(#${id}-shell)`} />
      <rect x="91" y="62" width="138" height="98" rx="42" fill={`url(#${id}-visor)`} />
      <path d="M108 80 Q130 68 158 68" fill="none" stroke="#fff" strokeOpacity=".16" strokeWidth="5" strokeLinecap="round" />
      <Face cx={160} cy={105} mood={mood} x={x} y={y} id={id} />
    </g>
  );
}

/** Sofía de cuerpo entero. */
export function Robot({ mood = "idle", className = "" }: { mood?: Mood; className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const id = useId().replace(/:/g, "");
  const { x, y } = useEyeTracking(ref, 9);
  return (
    <motion.svg
      ref={ref}
      viewBox="0 0 320 420"
      className={className}
      role="img"
      aria-label="Sofía, Operativa.ia's robot assistant"
      animate={{ y: [0, -14, 0], rotate: [-1, 1, -1] }}
      transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
    >
      <Defs id={id} />
      <motion.ellipse
        cx="160"
        cy="405"
        rx="82"
        ry="10"
        fill="#FF5A1F"
        opacity=".35"
        animate={{ scaleX: [1, 0.82, 1], opacity: [0.38, 0.2, 0.38] }}
        transition={{ duration: 5, repeat: Infinity, ease: "easeInOut" }}
        style={{ transformBox: "fill-box", transformOrigin: "center" }}
      />
      <motion.path
        d="M84 226 C50 240 38 282 54 316 C62 332 84 326 84 308 C82 284 92 266 106 254 Z"
        fill={`url(#${id}-body)`}
        style={{ transformBox: "fill-box", transformOrigin: "90% 10%" }}
        animate={{ rotate: [0, 3, 0] }}
        transition={{ duration: 3.4, repeat: Infinity, ease: "easeInOut" }}
      />
      <motion.path
        d="M236 226 C270 214 288 180 278 146 C272 128 248 132 246 150 C246 172 232 190 214 204 Z"
        fill={`url(#${id}-body)`}
        style={{ transformBox: "fill-box", transformOrigin: "10% 90%" }}
        animate={{ rotate: [0, -12, 6, -12, 0, 0, 0] }}
        transition={{ duration: 4.5, repeat: Infinity, ease: "easeInOut", times: [0, 0.1, 0.2, 0.3, 0.4, 0.7, 1] }}
      />
      <path d="M160 190 C102 190 78 244 84 306 C90 362 122 392 160 392 C198 392 230 362 236 306 C242 244 218 190 160 190 Z" fill={`url(#${id}-body)`} />
      <path d="M100 318 Q160 352 220 318" fill="none" stroke="#B9A194" strokeOpacity=".55" strokeWidth="3" />
      <motion.circle
        cx="160"
        cy="262"
        r="15"
        fill={`url(#${id}-eye)`}
        filter={`url(#${id}-glow)`}
        animate={{ scale: [1, 1.2, 1], opacity: [1, 0.72, 1] }}
        transition={{ duration: 2.2, repeat: Infinity, ease: "easeInOut" }}
        style={{ transformBox: "fill-box", transformOrigin: "center" }}
      />
      <Head id={id} mood={mood} x={x} y={y} />
    </motion.svg>
  );
}

/** Solo la cabeza: para el botón del chat y los avatares. */
export function RobotHead({ mood = "idle", className = "" }: { mood?: Mood; className?: string }) {
  const ref = useRef<SVGSVGElement>(null);
  const id = useId().replace(/:/g, "");
  const { x, y } = useEyeTracking(ref, 7);
  return (
    <svg ref={ref} viewBox="52 0 216 190" className={className} aria-hidden="true">
      <Defs id={id} />
      <Head id={id} mood={mood} x={x} y={y} />
    </svg>
  );
}
