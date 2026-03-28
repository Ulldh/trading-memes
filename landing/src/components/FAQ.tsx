"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";

const faqs = [
  {
    question: "¿Qué es un gem?",
    answer:
      "Un token que sube 10x o más desde su precio inicial. Nuestro modelo clasifica tokens en 5 categorías: rug (pérdida total), loss (>50% caída), neutral, winner (2-10x), y gem (10x+).",
  },
  {
    question: "¿Cómo funciona el modelo ML?",
    answer:
      "Ensemble de Random Forest + XGBoost + LightGBM. Entrenado con 94 features extraídas de 5,000+ tokens. Métricas actuales: F1 Score 0.667, Precision 0.726. El modelo analiza tokenomics, liquidez, price action, concentración de holders y contexto de mercado.",
  },
  {
    question: "¿Qué blockchains soportáis?",
    answer:
      "Solana, Ethereum y Base. Datos recopilados de GeckoTerminal (precio/volumen), DexScreener (buyers/sellers), Helius RPC (holders Solana), Etherscan (verificación de contratos) y Birdeye (datos complementarios).",
  },
  {
    question: "¿Con qué frecuencia se actualizan las señales?",
    answer:
      "Recolección diaria a las 06:00 UTC. Scoring a las 07:30 UTC. El modelo se reentrena semanalmente con drift detection automático — si la distribución de datos cambia significativamente, se dispara un retrain anticipado.",
  },
  {
    question: "¿Puedo perder dinero?",
    answer:
      "Sí. Los memecoins son extremadamente volátiles. Nuestro modelo acierta ~67% de las veces. El 33% restante son pérdidas. Esto NO es consejo financiero. DYOR (Do Your Own Research). Nunca inviertas más de lo que puedas permitirte perder.",
  },
  {
    question: "¿Puedo cancelar en cualquier momento?",
    answer:
      "Sí. Sin permanencia ni compromiso. Cancela desde tu perfil o directamente desde el portal de Stripe. Tu acceso continúa hasta el final del período facturado.",
  },
  {
    question: "¿Qué datos recopiláis?",
    answer:
      "Email y Telegram ID (opcional para alertas). No vendemos datos a terceros. Cumplimiento total con RGPD. Puedes solicitar la eliminación de tus datos en cualquier momento. Ver nuestra Política de Privacidad.",
  },
];

function FAQItem({
  faq,
  index,
}: {
  faq: { question: string; answer: string };
  index: number;
}) {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.4, delay: index * 0.08 }}
      className="border-b border-dark-600"
    >
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between py-5 text-left group"
      >
        <span className="text-sm md:text-base text-primary group-hover:glow-green transition-all duration-200">
          <span className="text-dark-600 mr-3">
            {String(index + 1).padStart(2, "0")}.
          </span>
          {faq.question}
        </span>
        <span
          className={`text-dark-600 text-lg ml-4 transition-transform duration-200 ${
            isOpen ? "rotate-45" : ""
          }`}
        >
          +
        </span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <p className="text-sm text-gray-400 leading-relaxed pb-5 pl-8 pr-4">
              {faq.answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function FAQ() {
  return (
    <section id="faq" className="py-24 px-6 bg-dark-900">
      <div className="max-w-3xl mx-auto">
        {/* Section header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="text-center mb-16"
        >
          <p className="text-xs text-dark-600 tracking-widest uppercase mb-4">
            <span className="text-primary">$</span> man meme-detector
          </p>
          <h2 className="text-3xl md:text-4xl font-bold">
            Preguntas frecuentes
          </h2>
        </motion.div>

        {/* Questions */}
        <div className="border-t border-dark-600">
          {faqs.map((faq, index) => (
            <FAQItem key={index} faq={faq} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
