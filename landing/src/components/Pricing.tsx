"use client";

import { motion } from "framer-motion";
import { useTranslations } from "next-intl";

// URLs de pago (no se traducen)
const planHrefs = [
  "https://app.memedetector.es/?tab=register",
  "https://buy.stripe.com/bJe8wPgnT7Ai6RT4xCaZi00",
  "https://buy.stripe.com/8x2fZh4Fbg6Oekld48aZi01",
];

export default function Pricing() {
  const t = useTranslations("pricing");

  const plans = Array.from({ length: 3 }, (_, i) => ({
    name: t(`plans.${i}.name`),
    price: t(`plans.${i}.price`),
    period: t(`plans.${i}.period`),
    highlighted: i === 1,
    badge: i === 1 ? "\u2605" : undefined,
    features: t.raw(`plans.${i}.features`) as Array<{ text: string; included: boolean }>,
    cta: t(`plans.${i}.cta`),
    href: planHrefs[i],
  }));

  return (
    <section id="pricing" className="py-24 px-6 bg-dark-900">
      <div className="max-w-6xl mx-auto">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-xs text-gray-500 tracking-widest uppercase mb-4">
            <span className="text-primary">$</span> {t("terminal_prompt").replace("$ ", "")}
          </p>
          <h2 className="text-3xl md:text-4xl font-bold">
            {t("section_title")}
          </h2>
        </motion.div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {plans.map((plan, index) => (
            <motion.div
              key={index}
              initial={{ opacity: 0, y: 30 }}
              whileInView={{ opacity: 1, y: 0 }}
              viewport={{ once: true }}
              transition={{ duration: 0.5, delay: index * 0.15 }}
              className={`relative border p-8 flex flex-col ${
                plan.highlighted
                  ? "border-primary"
                  : "border-dark-600"
              }`}
              style={
                plan.highlighted
                  ? {
                      boxShadow:
                        "0 0 20px rgba(0, 212, 170, 0.15), 0 0 40px rgba(0, 212, 170, 0.05)",
                    }
                  : undefined
              }
            >
              {/* Plan name + badge */}
              <div className="flex items-center gap-3 mb-6">
                <h3 className="text-lg font-bold tracking-wider">
                  {plan.name}
                </h3>
                {plan.badge && (
                  <span className="text-primary text-sm">{plan.badge}</span>
                )}
              </div>

              {/* Price */}
              <div className="mb-8">
                <span
                  className={`text-4xl font-bold ${
                    plan.highlighted ? "text-primary glow-green" : ""
                  }`}
                >
                  {plan.price}
                </span>
                <span className="text-gray-500 text-sm">{plan.period}</span>
                {plan.highlighted && (
                  <p className="text-xs text-primary/70 mt-2 font-mono">
                    {t("pro_anchor")}
                  </p>
                )}
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-10 flex-1">
                {plan.features.map((feature, fi) => (
                  <li key={fi} className="flex items-center gap-3 text-sm">
                    {feature.included ? (
                      <span className="text-primary font-bold" aria-hidden="true">{"\u2713"}</span>
                    ) : (
                      <span className="text-gray-600 font-bold" aria-hidden="true">{"\u2717"}</span>
                    )}
                    <span
                      className={
                        feature.included ? "text-gray-300" : "text-gray-600"
                      }
                    >
                      <span className="sr-only">{feature.included ? "Incluido: " : "No incluido: "}</span>
                      {feature.text}
                    </span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <a
                href={plan.href}
                target="_blank"
                rel="noopener noreferrer"
                className={`block text-center py-3 px-6 text-sm font-semibold tracking-wider uppercase transition-all duration-300 ${
                  plan.highlighted
                    ? "border-2 border-primary text-primary hover:bg-primary hover:text-dark-900"
                    : "border border-dark-600 text-gray-400 hover:border-gray-400 hover:text-white"
                }`}
              >
                {plan.cta}
              </a>
              {/* Nota para planes de pago: usar mismo email */}
              {index > 0 && (
                <p className="text-xs text-gray-500 text-center mt-3">
                  {t("plans.email_note")}
                </p>
              )}
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
