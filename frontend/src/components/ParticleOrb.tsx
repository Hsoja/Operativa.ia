import { useEffect, useRef } from "react";

const COUNT_DESKTOP = 4200;
const COUNT_MOBILE = 2600;

interface Point {
  x: number;
  y: number;
  z: number;
}

function fibonacciSphere(count: number): Point[] {
  const golden = Math.PI * (3 - Math.sqrt(5));
  return Array.from({ length: count }, (_, i) => {
    const y = 1 - (i / (count - 1)) * 2;
    const radius = Math.sqrt(1 - y * y);
    const theta = golden * i;
    return { x: Math.cos(theta) * radius, y, z: Math.sin(theta) * radius };
  });
}

/** Orbe de partículas que se deforma como una voz. `energy` lo agita mientras Sofía piensa. */
export function ParticleOrb({ className = "", energy = 0, density = 1 }: { className?: string; energy?: number; density?: number }) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const energyRef = useRef(energy);
  energyRef.current = energy;

  useEffect(() => {
    const canvas = canvasRef.current;
    const ctx = canvas?.getContext("2d");
    if (!canvas || !ctx) return;

    const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    const small = window.innerWidth < 768;
    const points = fibonacciSphere(Math.round((small ? COUNT_MOBILE : COUNT_DESKTOP) * density));
    let width = 0;
    let height = 0;
    let frame = 0;
    let visible = true;
    let currentEnergy = 0;
    let pointerX = 0;
    let pointerY = 0;

    const resize = () => {
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      const box = canvas.getBoundingClientRect();
      width = box.width;
      height = box.height;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(height * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    };

    const draw = (ms: number) => {
      const t = ms * 0.00042;
      currentEnergy += (energyRef.current - currentEnergy) * 0.05;
      const amp = 0.17 + currentEnergy * 0.17;
      const speed = 1 + currentEnergy * 2.4;
      const radius = Math.min(width, height) * 0.36;
      // Las partículas crecen con el orbe para que uno grande no se vea apagado
      const dot = Math.max(0.75, Math.min(small ? 1 : 1.6, radius / 130));
      const cx = width / 2;
      const cy = height / 2;
      const rotY = t * 0.75 + pointerX * 0.5;
      const rotX = 0.35 + Math.sin(t * 0.5) * 0.22 + pointerY * 0.35;
      const cosY = Math.cos(rotY);
      const sinY = Math.sin(rotY);
      const cosX = Math.cos(rotX);
      const sinX = Math.sin(rotX);

      ctx.clearRect(0, 0, width, height);
      ctx.globalCompositeOperation = "lighter";

      for (const p of points) {
        const wave =
          Math.sin(p.x * 2.6 + t * 2.4 * speed) * Math.cos(p.y * 3.1 - t * 1.8 * speed) +
          0.55 * Math.sin(p.z * 4.2 + t * 3.1 * speed + p.x * 2) +
          0.3 * Math.cos(p.y * 7 + t * 4 * speed);
        const scale = 1 + wave * amp;
        const x0 = p.x * scale;
        const y0 = p.y * scale;
        const z0 = p.z * scale;
        const x1 = x0 * cosY + z0 * sinY;
        const z1 = -x0 * sinY + z0 * cosY;
        const y1 = y0 * cosX - z1 * sinX;
        const z2 = y0 * sinX + z1 * cosX;
        const depth = (z2 + 1.3) / 2.6;
        const perspective = 1 / (1.9 - z2 * 0.42);
        const px = cx + x1 * radius * perspective * 1.9;
        const py = cy + y1 * radius * perspective * 1.9;
        const size = (0.6 + depth * 1.45) * dot;
        // Del rojo profundo al ámbar según la profundidad y la deformación
        const mix = Math.min(1, Math.max(0, depth * 0.72 + wave * 0.2));
        const r = 232 + mix * 23;
        const g = 28 + mix * 176;
        const b = 62 + mix * 62;
        ctx.fillStyle = `rgba(${r | 0},${g | 0},${b | 0},${0.26 + depth * 0.74})`;
        ctx.fillRect(px, py, size, size);
      }
      ctx.globalCompositeOperation = "source-over";
    };

    const loop = (ms: number) => {
      if (visible && !document.hidden) draw(ms);
      frame = requestAnimationFrame(loop);
    };

    const onPointer = (event: PointerEvent) => {
      pointerX = event.clientX / window.innerWidth - 0.5;
      pointerY = event.clientY / window.innerHeight - 0.5;
    };

    resize();
    const observer = new IntersectionObserver(([entry]) => (visible = entry.isIntersecting));
    observer.observe(canvas);
    const resizeObserver = new ResizeObserver(() => {
      resize();
      if (reduced) draw(4000);
    });
    resizeObserver.observe(canvas);

    if (reduced) {
      draw(4000);
    } else {
      frame = requestAnimationFrame(loop);
      window.addEventListener("pointermove", onPointer, { passive: true });
    }

    return () => {
      cancelAnimationFrame(frame);
      observer.disconnect();
      resizeObserver.disconnect();
      window.removeEventListener("pointermove", onPointer);
    };
  }, [density]);

  return <canvas ref={canvasRef} className={className} aria-hidden="true" />;
}
