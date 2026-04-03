"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { useStats } from "@/hooks/useStats";

interface VersionEntry {
  version: string;
  date: string;
  gems: number;
  features: number;
  rf_f1: number;
  highlights: string[];
  isCurrent: boolean;
}

// Historial de versiones anteriores (estatico — ya no cambian)
const previousVersions: VersionEntry[] = [
  {
    version: "v21",
    date: "2026-03-28",
    gems: 194,
    features: 22,
    rf_f1: 0.449,
    highlights: ["52% STRONG gem rate", "71% win rate (2x+)"],
    isCurrent: false,
  },
  {
    version: "v19",
    date: "2026-03-26",
    gems: 150,
    features: 20,
    rf_f1: 0.5,
    highlights: ["Clean baseline after data leakage fix"],
    isCurrent: false,
  },
];

export default function ModelChangelog() {
  const t = useTranslations("changelog");
  const stats = useStats();

  // La version actual se construye dinámicamente desde la API
  const currentVersion: VersionEntry = {
    version: stats.model_version,
    date: new Date().toISOString().split("T")[0],
    gems: stats.gems,
    features: stats.features_count,
    rf_f1: stats.auc, // Usamos AUC como métrica principal visible
    highlights: [
      `${Math.round(stats.hit_rate * 100)}% STRONG gem rate`,
      `${Math.round(stats.win_rate * 100)}% win rate (2x+)`,
    ],
    isCurrent: true,
  };

  const versions = [currentVersion, ...previousVersions];

  return (
    <section className="relative py-20 px-4 bg-dark-900">
      {/* Linea vertical central decorativa (desktop) */}
      <div className="hidden md:block absolute left-1/2 top-24 bottom-24 w-px bg-dark-600" />

      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-16"
        >
          <p className="text-xs text-primary font-mono uppercase tracking-widest mb-3">
            $ git log --oneline
          </p>
          <h2 className="text-3xl md:text-4xl font-bold mb-3">{t("title")}</h2>
          <p className="text-gray-500 text-sm max-w-xl mx-auto">{t("subtitle")}</p>
        </motion.div>

        {/* Timeline */}
        <div className="relative space-y-8">
          {versions.map((v, i) => (
            <motion.div
              key={v.version}
              initial={{ opacity: 0, x: i % 2 === 0 ? -30 : 30 }}
              whileInView={{ opacity: 1, x: 0 }}
              viewport={{ once: true, amount: 0.3 }}
              transition={{ duration: 0.5, delay: i * 0.1 }}
              className="relative"
            >
              {/* Nodo de conexion (desktop) */}
              <div className="hidden md:flex absolute left-1/2 top-6 -translate-x-1/2 z-10">
                <div
                  className={`w-3 h-3 rounded-full border-2 ${
                    v.isCurrent
                      ? "bg-primary border-primary shadow-[0_0_10px_rgba(0,212,170,0.6)]"
                      : "bg-dark-800 border-dark-600"
                  }`}
                />
              </div>

              {/* Card */}
              <div
                className={`md:w-[45%] ${
                  i % 2 === 0 ? "md:mr-auto md:pr-8" : "md:ml-auto md:pl-8"
                }`}
              >
                <div
                  className={`border p-5 ${
                    v.isCurrent
                      ? "border-primary/40 shadow-[0_0_15px_rgba(0,212,170,0.1)]"
                      : "border-dark-600"
                  } bg-dark-800`}
                >
                  {/* Cabecera: version badge + fecha */}
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span
                        className={`font-mono text-sm font-bold px-2 py-0.5 ${
                          v.isCurrent
                            ? "bg-primary/20 text-primary border border-primary/30"
                            : "bg-dark-700 text-gray-400 border border-dark-600"
                        }`}
                      >
                        {v.version}
                      </span>
                      {v.isCurrent && (
                        <span className="text-[10px] text-primary font-mono uppercase tracking-wider animate-pulse">
                          {t("current")}
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-gray-500 font-mono">{v.date}</span>
                  </div>

                  {/* Metricas */}
                  <div className="grid grid-cols-3 gap-3 mb-3">
                    <div className="text-center">
                      <p className="text-lg font-bold text-primary font-mono">
                        {v.rf_f1.toFixed(3)}
                      </p>
                      <p className="text-[10px] text-gray-500 font-mono uppercase">
                        {v.isCurrent ? "AUC" : "RF F1"}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-gem-yellow font-mono">{v.gems}</p>
                      <p className="text-[10px] text-gray-500 font-mono uppercase">
                        {t("gems")}
                      </p>
                    </div>
                    <div className="text-center">
                      <p className="text-lg font-bold text-gray-300 font-mono">{v.features}</p>
                      <p className="text-[10px] text-gray-500 font-mono uppercase">
                        {t("features")}
                      </p>
                    </div>
                  </div>

                  {/* Highlights */}
                  <div className="space-y-1">
                    {v.highlights.map((h, j) => (
                      <p key={j} className="text-xs text-gray-400 font-mono">
                        <span className="text-primary mr-1">+</span>
                        {h}
                      </p>
                    ))}
                  </div>
                </div>
              </div>

              {/* Flecha entre versiones (excepto la ultima) */}
              {i < versions.length - 1 && (
                <div className="hidden md:flex justify-center my-2">
                  <span className="text-dark-600 text-lg">&#8595;</span>
                </div>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
