"use client";

import { motion } from "framer-motion";

const plans = [
  {
    name: "FREE",
    price: "$0",
    period: "/mes",
    highlighted: false,
    features: [
      { text: "3 señales/día", included: true },
      { text: "Watchlist (3)", included: true },
      { text: "Token search", included: false },
      { text: "Telegram alerts", included: false },
      { text: "Backtesting", included: false },
    ],
    cta: "Crear cuenta",
    href: "https://app.memedetector.es",
  },
  {
    name: "PRO",
    badge: "★",
    price: "$29",
    period: "/mes",
    highlighted: true,
    features: [
      { text: "Todas las señales", included: true },
      { text: "Token search", included: true },
      { text: "Telegram alerts", included: true },
      { text: "Watchlist (10)", included: true },
      { text: "SHAP analysis", included: true },
      { text: "Track record", included: true },
    ],
    cta: "Empezar →",
    href: "https://buy.stripe.com/bJe8wPgnT7Ai6RT4xCaZi00",
  },
  {
    name: "ENTERPRISE",
    price: "$99",
    period: "/mes",
    highlighted: false,
    features: [
      { text: "Todo de Pro", included: true },
      { text: "API access", included: true },
      { text: "Watchlist ∞", included: true },
      { text: "Soporte prioritario", included: true },
      { text: "Datos export", included: true },
    ],
    cta: "Contactar",
    href: "mailto:info@memedetector.es?subject=Enterprise",
  },
];

export default function Pricing() {
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
          <p className="text-xs text-dark-600 tracking-widest uppercase mb-4">
            <span className="text-primary">$</span> cat /plans
          </p>
          <h2 className="text-3xl md:text-4xl font-bold">
            Acceso
          </h2>
        </motion.div>

        {/* Cards grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
          {plans.map((plan, index) => (
            <motion.div
              key={plan.name}
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
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-10 flex-1">
                {plan.features.map((feature) => (
                  <li key={feature.text} className="flex items-center gap-3 text-sm">
                    {feature.included ? (
                      <span className="text-primary font-bold">✓</span>
                    ) : (
                      <span className="text-gray-600 font-bold">✗</span>
                    )}
                    <span
                      className={
                        feature.included ? "text-gray-300" : "text-gray-600"
                      }
                    >
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
