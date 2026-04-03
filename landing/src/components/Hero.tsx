"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import { useStats } from "@/hooks/useStats";
import Countdown from "./Countdown";

// Formatea hit rate de 0.52 a "52%"
function fmtPct(v: number): string {
  return `${Math.round(v * 100)}%`;
}

// Calcula "vs random" — cuantas veces mejor que azar (gem rate ~5% base)
function vsRandom(hitRate: number): string {
  const base = 0.05; // ~5% de tokens son gems de forma aleatoria
  return `${(hitRate / base).toFixed(1)}x`;
}

export default function Hero() {
  const t = useTranslations("hero");
  const stats = useStats();

  return (
    <section className="relative min-h-screen flex items-center justify-center matrix-bg overflow-hidden">
      {/* Scanline overlay */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          backgroundImage:
            "repeating-linear-gradient(0deg, transparent, transparent 2px, rgba(0,212,170,0.015) 2px, rgba(0,212,170,0.015) 4px)",
        }}
      />

      {/* Subtle grid */}
      <div
        className="absolute inset-0 pointer-events-none opacity-[0.03]"
        style={{
          backgroundImage:
            "linear-gradient(rgba(0,212,170,1) 1px, transparent 1px), linear-gradient(90deg, rgba(0,212,170,1) 1px, transparent 1px)",
          backgroundSize: "60px 60px",
        }}
      />

      <div className="relative z-10 max-w-5xl mx-auto px-6 text-center">
        {/* Terminal prompt */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.5 }}
          className="mb-8 text-xs text-gray-500 tracking-widest uppercase"
        >
          <span className="text-primary">$</span> meme-detector
          <span className="text-primary"> --</span>scan
          <span className="text-primary"> --</span>live
          <span className="ml-2 inline-block w-2 h-4 bg-primary animate-pulse" />
        </motion.div>

        {/* Main title */}
        <motion.h1
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.2 }}
          className="text-4xl md:text-6xl lg:text-7xl font-bold leading-tight mb-6"
        >
          {t("title_line1")}{" "}
          <span className="text-primary glow-green">{t("title_highlight")}</span>
          <br />
          {t("title_line2")}
        </motion.h1>

        {/* Subtitle — tokens analizados dinámico */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="text-lg md:text-xl text-gray-400 mb-10 max-w-2xl mx-auto"
        >
          {t("subtitle_prefix")}{" "}
          <span className="text-primary font-semibold">
            {stats.tokens.toLocaleString("es-ES")}+
          </span>{" "}
          {t("subtitle_suffix")}
        </motion.p>

        {/* Three stats — dinámicos desde API */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.6 }}
          className="flex flex-wrap justify-center gap-8 mb-12 text-sm"
        >
          <div className="border border-dark-600 px-5 py-3">
            <span className="text-primary font-bold text-lg">{stats.gems.toLocaleString("es-ES")}</span>
            <span className="text-gray-500 ml-2">{t("stat_gems")}</span>
          </div>
          <div className="border border-dark-600 px-5 py-3">
            <span className="text-primary font-bold text-lg">{fmtPct(stats.hit_rate)}</span>
            <span className="text-gray-500 ml-2">{t("stat_hit_rate")}</span>
          </div>
          <div className="border border-dark-600 px-5 py-3">
            <span className="text-primary font-bold text-lg">{vsRandom(stats.hit_rate)}</span>
            <span className="text-gray-500 ml-2">{t("stat_vs_random")}</span>
          </div>
        </motion.div>

        {/* Countdown hasta proximo scan */}
        <div className="mb-8">
          <Countdown />
        </div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8 }}
        >
          <div className="flex gap-4 justify-center flex-wrap">
            <a
              href="https://app.memedetector.es/?tab=register"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block border-2 border-primary text-primary px-8 py-4 text-sm font-semibold tracking-wider uppercase hover:bg-primary hover:text-dark-900 transition-all duration-300"
            >
              {t("cta_signup")}
            </a>
            <a
              href="https://app.memedetector.es/?tab=login"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block border-2 border-dark-600 text-gray-400 px-8 py-4 text-sm font-semibold tracking-wider uppercase hover:border-gray-400 hover:text-white transition-all duration-300"
            >
              {t("cta_login")}
            </a>
          </div>
        </motion.div>

        {/* Bottom terminal line — métricas dinámicas */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.2 }}
          className="mt-16 text-xs text-gray-500 font-mono"
        >
          <span className="text-gem-green">{t("status_label")}</span> {t("status_value")} &middot;{" "}
          <span className="text-gem-green">{t("model_label")}</span> {stats.model_version} &middot;{" "}
          <span className="text-gem-green">{t("f1_label")}</span> {stats.auc.toFixed(3)} &middot;{" "}
          <span className="text-gem-green">{t("precision_label")}</span> {fmtPct(stats.recall)}
        </motion.div>

        {/* Disclaimer banner */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.5 }}
          className="mt-6 text-[10px] sm:text-xs text-gray-500"
        >
          {t("disclaimer_text")}{" "}
          <a
            href="/disclaimer"
            className="text-gem-yellow/70 hover:text-gem-yellow underline underline-offset-2 transition-colors"
          >
            {t("disclaimer_link")}
          </a>
          .
        </motion.div>
      </div>
    </section>
  );
}
