"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";

export default function FinalCTA(): React.JSX.Element {
  const t = useTranslations("final_cta");

  return (
    <section className="relative py-24 px-4 bg-dark-900 border-t border-dark-600 overflow-hidden">
      {/* Glow de fondo */}
      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          background:
            "radial-gradient(ellipse 60% 40% at 50% 50%, rgba(0,212,170,0.06) 0%, transparent 70%)",
        }}
      />

      <div className="max-w-2xl mx-auto text-center relative">
        {/* Headline emocional */}
        <motion.h2
          initial={{ opacity: 0, y: 24 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.6 }}
          className="text-3xl md:text-4xl font-bold font-mono text-white leading-tight mb-8"
        >
          {t("headline")}
        </motion.h2>

        {/* CTA button */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.5, delay: 0.15 }}
        >
          <a
            href="https://app.memedetector.es/?tab=register"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-3 bg-primary text-dark-900 font-mono font-bold text-base px-10 py-4 hover:bg-primary/90 transition-all duration-200 shadow-lg shadow-primary/20"
          >
            {t("cta_button")}
          </a>
        </motion.div>

        {/* Sub-texto */}
        <motion.p
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true, amount: 0.5 }}
          transition={{ duration: 0.5, delay: 0.3 }}
          className="text-xs text-gray-500 font-mono mt-5 tracking-wide"
        >
          {t("subtext")}
        </motion.p>
      </div>
    </section>
  );
}
