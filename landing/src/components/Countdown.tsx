"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";

// Calcula los segundos hasta el proximo pipeline run (06:00 o 18:00 UTC)
function getSecondsUntilNextRun(): number {
  const now = new Date();
  const utcH = now.getUTCHours();
  const utcM = now.getUTCMinutes();
  const utcS = now.getUTCSeconds();
  const totalNowSecs = utcH * 3600 + utcM * 60 + utcS;

  // Proximos runs: 06:00 UTC (21600s) y 18:00 UTC (64800s)
  const runs = [6 * 3600, 18 * 3600];

  let best = Infinity;
  for (const run of runs) {
    let diff = run - totalNowSecs;
    if (diff <= 0) diff += 86400; // siguiente dia
    if (diff < best) best = diff;
  }

  return best;
}

// Formatea segundos a HH:MM:SS
function formatTime(totalSecs: number): string {
  const h = Math.floor(totalSecs / 3600);
  const m = Math.floor((totalSecs % 3600) / 60);
  const s = totalSecs % 60;
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
}

export default function Countdown() {
  const t = useTranslations("countdown");
  const [secs, setSecs] = useState<number | null>(null);

  useEffect(() => {
    // Inicializar en el cliente para evitar hydration mismatch
    setSecs(getSecondsUntilNextRun());

    const interval = setInterval(() => {
      setSecs(getSecondsUntilNextRun());
    }, 1000);

    return () => clearInterval(interval);
  }, []);

  // No renderizar nada en SSR para evitar mismatch
  if (secs === null) return null;

  // Si estamos dentro de los 2 minutos del run, mostrar "escaneando"
  const isRunning = secs > 86400 - 120 || secs < 1;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5, delay: 1.0 }}
      className="flex items-center justify-center gap-2 text-xs font-mono"
    >
      <span className="text-primary opacity-70">&gt;</span>
      <span className="text-gray-500">
        {isRunning ? (
          <span className="text-primary animate-pulse">{t("running")}</span>
        ) : (
          <>
            {t("next_scan")}{" "}
            <span className="text-primary tabular-nums">{formatTime(secs)}</span>
          </>
        )}
      </span>
    </motion.div>
  );
}
