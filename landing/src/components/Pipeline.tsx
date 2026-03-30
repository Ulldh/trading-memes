"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";

const containerVariants = {
  hidden: {},
  visible: {
    transition: { staggerChildren: 0.2 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 40 },
  visible: {
    opacity: 1,
    y: 0,
    transition: { duration: 0.6, ease: "easeOut" },
  },
};

export default function Pipeline() {
  const t = useTranslations("pipeline");

  // Iconos de cada paso (no se traducen)
  const stepIcons = ["{ }", "f(x)", "ML", ">>"];

  // Construir los pasos desde las traducciones
  const steps = Array.from({ length: 4 }, (_, i) => ({
    title: t(`steps.${i}.title`),
    icon: stepIcons[i],
    stats: t.raw(`steps.${i}.stats`) as string[],
    detail: t(`steps.${i}.detail`),
  }));

  return (
    <section id="pipeline" className="relative py-24 px-4 bg-dark-900">
      {/* Section title */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true, amount: 0.3 }}
        transition={{ duration: 0.5 }}
        className="text-center mb-16"
      >
        <h2 className="text-3xl md:text-5xl font-bold text-primary glow-green font-mono">
          {t("section_title")}
          <span className="inline-block w-[2px] h-[1em] bg-primary ml-2 animate-pulse align-middle" />
        </h2>
        <p className="text-gray-500 text-sm mt-4 font-mono tracking-wide uppercase">
          {t("section_subtitle")}
        </p>
      </motion.div>

      {/* Pipeline flow */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        whileInView="visible"
        viewport={{ once: true, amount: 0.15 }}
        className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-4 gap-0 items-stretch"
      >
        {steps.map((step, i) => (
          <div key={i} className="flex items-stretch">
            {/* Card */}
            <motion.div variants={cardVariants} className="flex-1 flex flex-col">
              <div className="border border-dark-600 bg-dark-800 p-6 flex flex-col h-full hover:border-primary/50 transition-colors duration-300">
                {/* Header */}
                <div className="flex items-center gap-3 mb-4">
                  <span className="text-primary font-mono text-xs border border-primary/30 px-2 py-1 bg-primary/5">
                    {step.icon}
                  </span>
                  <h3 className="text-primary font-mono font-bold text-lg tracking-wider">
                    {step.title}
                  </h3>
                </div>

                {/* Stats list */}
                <ul className="space-y-2 mb-4 flex-1">
                  {step.stats.map((stat, si) => (
                    <li
                      key={si}
                      className="text-sm font-mono text-gray-400 flex items-start gap-2"
                    >
                      <span className="text-primary mt-0.5 text-xs">{">"}</span>
                      {stat}
                    </li>
                  ))}
                </ul>

                {/* Detail */}
                <p className="text-xs text-gray-600 font-mono leading-relaxed border-t border-dark-600 pt-3 mt-auto">
                  {step.detail}
                </p>
              </div>
            </motion.div>

            {/* Arrow connector (not after last) */}
            {i < steps.length - 1 && (
              <div className="hidden md:flex items-center justify-center w-12 flex-shrink-0">
                <div className="relative w-full h-[2px]">
                  {/* Dashed line */}
                  <div className="absolute inset-0 border-t-2 border-dashed border-primary/30" />
                  {/* Flowing animation overlay */}
                  <div
                    className="absolute inset-0 h-[2px] overflow-hidden"
                    style={{
                      background:
                        "repeating-linear-gradient(90deg, #00d4aa 0px, #00d4aa 4px, transparent 4px, transparent 12px)",
                      backgroundSize: "200% 100%",
                      animation: "flowRight 1.5s linear infinite",
                    }}
                  />
                  {/* Arrowhead */}
                  <div className="absolute right-0 top-1/2 -translate-y-1/2 w-0 h-0 border-t-[5px] border-t-transparent border-b-[5px] border-b-transparent border-l-[8px] border-l-primary/60" />
                </div>
              </div>
            )}

            {/* Mobile arrow (vertical) */}
            {i < steps.length - 1 && (
              <div className="flex md:hidden items-center justify-center h-8 w-full absolute left-0" style={{ display: "none" }}>
                {/* handled by gap below */}
              </div>
            )}
          </div>
        ))}
      </motion.div>

      {/* Mobile vertical arrows */}
      <style jsx>{`
        @keyframes flowRight {
          0% {
            background-position: 0% 0;
          }
          100% {
            background-position: -100% 0;
          }
        }
      `}</style>
    </section>
  );
}
