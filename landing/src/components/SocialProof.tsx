"use client";

import { useEffect, useRef, useState } from "react";
import { motion, useInView } from "framer-motion";
import { useTranslations } from "next-intl";
import { useStats } from "@/hooks/useStats";

// Anima un número desde 0 hasta el valor objetivo cuando entra en pantalla
function CountUp({
  target,
  suffix = "",
  prefix = "",
  duration = 1800,
}: {
  target: number;
  suffix?: string;
  prefix?: string;
  duration?: number;
}): React.JSX.Element {
  const [value, setValue] = useState(0);
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, margin: "-100px" });

  useEffect(() => {
    if (!inView) return;

    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      // Ease-out cubic
      const eased = 1 - Math.pow(1 - progress, 3);
      setValue(Math.round(eased * target));
      if (progress < 1) requestAnimationFrame(tick);
    };

    requestAnimationFrame(tick);
  }, [inView, target, duration]);

  return (
    <span ref={ref}>
      {prefix}
      {value.toLocaleString("es-ES")}
      {suffix}
    </span>
  );
}

export default function SocialProof(): React.JSX.Element {
  const t = useTranslations("social_proof");
  const apiStats = useStats();

  // Valores dinámicos desde la API
  const stats = [
    {
      value: apiStats.signals,
      suffix: "",
      label: t("stat_signals"),
      icon: ">>",
      color: "text-primary",
    },
    {
      value: apiStats.gems,
      suffix: "",
      label: t("stat_gems"),
      icon: "◆",
      color: "text-gem-yellow",
    },
    {
      value: apiStats.tokens,
      suffix: "",
      label: t("stat_tokens"),
      icon: "{ }",
      color: "text-primary",
    },
    {
      value: null,
      suffix: "",
      label: t("stat_since"),
      icon: "~",
      color: "text-gray-400",
    },
  ];

  return (
    <section className="relative py-16 px-4 bg-dark-800 border-y border-dark-600">
      <div className="max-w-5xl mx-auto">
        {/* Stats row */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
          className="grid grid-cols-2 md:grid-cols-4 gap-6 md:gap-0 md:divide-x md:divide-dark-600"
        >
          {stats.map((stat, i) => (
            <div
              key={i}
              className="flex flex-col items-center justify-center text-center px-6 py-4"
            >
              <span className={`font-mono text-xs mb-2 ${stat.color} opacity-70`}>
                {stat.icon}
              </span>
              <p className={`text-3xl md:text-4xl font-bold font-mono ${stat.color} mb-1`}>
                {stat.value !== null ? (
                  <CountUp target={stat.value} suffix={stat.suffix} />
                ) : (
                  <span className="text-gray-300">{t("stat_since_value")}</span>
                )}
              </p>
              <p className="text-xs text-gray-500 font-mono uppercase tracking-widest">
                {stat.label}
              </p>
            </div>
          ))}
        </motion.div>

        {/* Tagline */}
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-center text-xs text-gray-500 font-mono tracking-widest uppercase mt-8"
        >
          {t("tagline")}
        </motion.p>
      </div>
    </section>
  );
}
