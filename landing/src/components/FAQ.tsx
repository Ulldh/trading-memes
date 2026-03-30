"use client";

import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { useTranslations } from "next-intl";

function FAQItem({
  question,
  answer,
  index,
}: {
  question: string;
  answer: string;
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
        aria-expanded={isOpen}
        aria-controls={`faq-answer-${index}`}
        id={`faq-question-${index}`}
        className="w-full flex items-center justify-between py-5 text-left group"
      >
        <span className="text-sm md:text-base text-primary group-hover:glow-green transition-all duration-200">
          <span className="text-gray-500 mr-3">
            {String(index + 1).padStart(2, "0")}.
          </span>
          {question}
        </span>
        <span
          aria-hidden="true"
          className={`text-gray-500 text-lg ml-4 transition-transform duration-200 ${
            isOpen ? "rotate-45" : ""
          }`}
        >
          +
        </span>
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            id={`faq-answer-${index}`}
            role="region"
            aria-labelledby={`faq-question-${index}`}
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.25 }}
            className="overflow-hidden"
          >
            <p className="text-sm text-gray-400 leading-relaxed pb-5 pl-8 pr-4">
              {answer}
            </p>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
}

export default function FAQ() {
  const t = useTranslations("faq");

  // Construir FAQs desde las traducciones
  const faqCount = 7; // Numero fijo de FAQs
  const faqs = Array.from({ length: faqCount }, (_, i) => ({
    question: t(`items.${i}.question`),
    answer: t(`items.${i}.answer`),
  }));

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
          <p className="text-xs text-gray-500 tracking-widest uppercase mb-4">
            <span className="text-primary">$</span> {t("terminal_prompt").replace("$ ", "")}
          </p>
          <h2 className="text-3xl md:text-4xl font-bold">
            {t("section_title")}
          </h2>
        </motion.div>

        {/* Questions */}
        <div className="border-t border-dark-600">
          {faqs.map((faq, index) => (
            <FAQItem key={index} question={faq.question} answer={faq.answer} index={index} />
          ))}
        </div>
      </div>
    </section>
  );
}
