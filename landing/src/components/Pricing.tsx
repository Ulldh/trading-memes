"use client";

import { useState } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";

// URLs de registro parametrizadas por plan (el dashboard maneja el flujo Stripe)
const planHrefs = [
  "https://app.memedetector.es/?tab=register&plan=free",
  "https://app.memedetector.es/?tab=register&plan=pro",
  "https://app.memedetector.es/?tab=register&plan=enterprise",
];

// Precios anuales (20% descuento vs mensual)
const annualPrices: Record<string, string> = {
  "0": "0",     // Free sigue siendo 0
  "29": "279",   // Pro: $279/ano (vs $348)
  "99": "949",   // Enterprise: $949/ano (vs $1,188)
};

// Extraer solo el numero del precio (ej: "$29" -> "29", "29 $" -> "29")
function extractPriceNumber(price: string): string {
  const match = price.match(/\d+/);
  return match ? match[0] : "0";
}

// Reemplazar el numero en el precio manteniendo el formato del locale
function replacePrice(original: string, newNumber: string): string {
  return original.replace(/\d+/, newNumber);
}

export default function Pricing() {
  const t = useTranslations("pricing");
  const [isAnnual, setIsAnnual] = useState(false);

  const plans = Array.from({ length: 3 }, (_, i) => {
    const monthlyPrice = t(`plans.${i}.price`);
    const monthlyPeriod = t(`plans.${i}.period`);
    const priceNum = extractPriceNumber(monthlyPrice);
    const annualNum = annualPrices[priceNum] || priceNum;

    // Calcular precio y periodo segun toggle
    const price = isAnnual && priceNum !== "0"
      ? replacePrice(monthlyPrice, annualNum)
      : monthlyPrice;
    const period = isAnnual && priceNum !== "0"
      ? monthlyPeriod.replace(/mes|mo|Monat|mois|mês/i, (m) => {
          const yearMap: Record<string, string> = {
            "mes": "año", "mo": "yr", "Monat": "Jahr", "mois": "an", "mês": "ano",
          };
          return yearMap[m] || "yr";
        })
      : monthlyPeriod;

    // Construir href con billing param
    const billingParam = isAnnual && priceNum !== "0" ? "&billing=annual" : "";
    const href = planHrefs[i] + billingParam;

    // CTA: mostrar "Prueba gratis 14 dias" para Pro mensual
    let cta = t(`plans.${i}.cta`);
    if (i === 1 && !isAnnual) {
      cta = t("pro_trial_cta");
    }

    return {
      name: t(`plans.${i}.name`),
      price,
      period,
      monthlyPrice: monthlyPrice,
      highlighted: i === 1,
      badge: i === 1 ? "\u2605" : undefined,
      features: t.raw(`plans.${i}.features`) as Array<{ text: string; included: boolean }>,
      cta,
      href,
      showSavings: isAnnual && priceNum !== "0",
    };
  });

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

          {/* Toggle mensual/anual */}
          <div className="flex items-center justify-center gap-4 mt-8">
            <span className={`text-sm font-semibold transition-colors ${!isAnnual ? "text-primary" : "text-gray-500"}`}>
              {t("billing_monthly")}
            </span>
            <button
              onClick={() => setIsAnnual(!isAnnual)}
              className={`relative w-14 h-7 rounded-full transition-colors duration-300 ${
                isAnnual ? "bg-primary" : "bg-dark-600"
              }`}
              aria-label={t("billing_toggle_label")}
            >
              <span
                className={`absolute top-0.5 left-0.5 w-6 h-6 rounded-full bg-white transition-transform duration-300 ${
                  isAnnual ? "translate-x-7" : ""
                }`}
              />
            </button>
            <span className={`text-sm font-semibold transition-colors ${isAnnual ? "text-primary" : "text-gray-500"}`}>
              {t("billing_annual")}
            </span>
            {isAnnual && (
              <span className="text-xs font-bold text-dark-900 bg-primary px-3 py-1 rounded-full">
                {t("billing_save")}
              </span>
            )}
          </div>
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
                {plan.showSavings && (
                  <p className="text-xs text-primary/70 mt-1 font-mono line-through-muted">
                    <span className="line-through text-gray-600">
                      {plan.monthlyPrice}{t(`plans.${index}.period`)}
                    </span>
                    {" "}{t("billing_save")}
                  </p>
                )}
                {plan.highlighted && !plan.showSavings && (
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
            </motion.div>
          ))}
        </div>
      </div>
    </section>
  );
}
