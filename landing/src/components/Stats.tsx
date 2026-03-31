"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { useTranslations } from "next-intl";

interface StatItem {
  value: number;
  suffix?: string;
  prefix?: string;
  label: string;
  decimals?: number;
}

interface StatsData {
  tokens: number;
  ohlcv: number;
  scores: number;
  gems: number;
}

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

    // Reset para re-animar si el target cambia
    startTime.current = null;

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

// Valores por defecto (actualizados 2026-03-29)
const DEFAULT_STATS: StatsData = {
  tokens: 5748,
  ohlcv: 134900,
  scores: 1389,
  gems: 140,
};

export default function Stats() {
  const t = useTranslations("stats");
  const [stats, setStats] = useState<StatsData>(DEFAULT_STATS);

  useEffect(() => {
    fetch("/api/stats")
      .then((r) => r.json())
      .then((data: StatsData) => {
        if (data && typeof data.tokens === "number") {
          setStats(data);
        }
      })
      .catch(() => {
        // Mantener valores por defecto
      });
  }, []);

  const statsData: StatItem[] = [
    { value: stats.tokens, label: t("items.0.label") },
    { value: stats.ohlcv, label: t("items.1.label") },
    { value: 94, label: t("items.2.label") },
    { value: 67, suffix: "%", label: t("items.3.label") },
    { value: 3, label: t("items.4.label") },
    { value: 7.3, label: t("items.5.label"), decimals: 1 },
    { value: 15, prefix: "<", suffix: "s", label: t("items.6.label") },
    { value: 24, suffix: "/7", label: t("items.7.label") },
  ];

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
            {t("section_title")}
          </h2>
          <p className="text-gray-400 text-sm mt-4 font-mono">
            {t("section_subtitle")}
          </p>
        </motion.div>

        {/* Stats grid */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {statsData.map((item, i) => (
            <StatCard key={i} item={item} index={i} />
          ))}
        </div>
      </div>
    </section>
  );
}
