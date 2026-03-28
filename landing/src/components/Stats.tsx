"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";

// TODO: Conectar a Supabase para obtener datos reales
// import { createClient } from "@supabase/supabase-js";
// const supabase = createClient(process.env.NEXT_PUBLIC_SUPABASE_URL!, process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!);

interface StatItem {
  value: number;
  suffix?: string;
  prefix?: string;
  label: string;
  decimals?: number;
}

const stats: StatItem[] = [
  { value: 5329, label: "tokens analizados" },
  { value: 88522, label: "candles OHLCV" },
  { value: 94, label: "features / token" },
  { value: 67, suffix: "%", label: "hit rate" },
  { value: 3, label: "blockchains" },
  { value: 7.3, label: "señales diarias (UTC)", decimals: 1 },
  { value: 15, prefix: "<", suffix: "s", label: "scoring time" },
  { value: 24, suffix: "/7", label: "monitoreo" },
];

function useCountUp(
  target: number,
  inView: boolean,
  duration = 2000,
  decimals = 0
): string {
  const [current, setCurrent] = useState(0);
  const startTime = useRef<number | null>(null);
  const rafId = useRef<number>(0);

  useEffect(() => {
    if (!inView) return;

    const animate = (timestamp: number) => {
      if (!startTime.current) startTime.current = timestamp;
      const elapsed = timestamp - startTime.current;
      const progress = Math.min(elapsed / duration, 1);

      // Ease out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setCurrent(eased * target);

      if (progress < 1) {
        rafId.current = requestAnimationFrame(animate);
      } else {
        setCurrent(target);
      }
    };

    rafId.current = requestAnimationFrame(animate);

    return () => {
      cancelAnimationFrame(rafId.current);
      startTime.current = null;
    };
  }, [inView, target, duration]);

  if (decimals > 0) {
    return current.toFixed(decimals);
  }
  return Math.round(current).toLocaleString("es-ES");
}

function StatCard({ item, index }: { item: StatItem; index: number }) {
  const ref = useRef(null);
  const isInView = useInView(ref, { once: true, amount: 0.5 });
  const display = useCountUp(item.value, isInView, 2000, item.decimals);

  return (
    <motion.div
      ref={ref}
      initial={{ opacity: 0, y: 30 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.5 }}
      transition={{ duration: 0.5, delay: index * 0.1 }}
      className="border border-dark-600 bg-dark-800/50 p-6 text-center hover:border-primary/30 transition-colors duration-300"
    >
      <div className="text-3xl md:text-4xl font-bold text-primary font-mono glow-green mb-2">
        {item.prefix ?? ""}
        {display}
        {item.suffix ?? ""}
      </div>
      <div className="text-xs text-gray-500 font-mono uppercase tracking-widest">
        {item.label}
      </div>
    </motion.div>
  );
}

export default function Stats() {
  return (
    <section id="stats" className="relative py-24 px-4 bg-dark-900">
      {/* Subtle grid background */}
      <div
        className="absolute inset-0 opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(#00d4aa 1px, transparent 1px), linear-gradient(90deg, #00d4aa 1px, transparent 1px)",
          backgroundSize: "40px 40px",
        }}
      />

      <div className="relative max-w-5xl mx-auto">
        {/* Section title */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <h2 className="text-3xl md:text-5xl font-bold text-white font-mono">
            Números que hablan
          </h2>
          <p className="text-gray-600 text-sm mt-4 font-mono">
            {/* TODO: Actualizar dinámicamente desde Supabase */}
            Datos actualizados del pipeline v12
          </p>
        </motion.div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {stats.map((item, i) => (
            <StatCard key={item.label} item={item} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
