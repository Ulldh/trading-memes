"use client";

import { motion } from "framer-motion";

export default function Footer() {
  return (
    <footer className="bg-dark-900 pt-12 pb-8 px-6">
      <div className="max-w-4xl mx-auto">
        {/* Top separator */}
        <div className="border-t border-dark-600 mb-10" />

        {/* Disclaimer */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6 }}
          className="border border-gem-yellow/30 bg-gem-yellow/5 p-6 mb-10"
        >
          <p className="text-xs md:text-sm text-gem-yellow leading-relaxed">
            <span className="font-bold">DISCLAIMER:</span> Meme Detector es una
            herramienta de análisis automatizado. No constituye asesoramiento
            financiero. Los memecoins son activos altamente especulativos y
            puedes perder la totalidad de tu inversión. DYOR.
          </p>
        </motion.div>

        {/* Bottom separator */}
        <div className="border-t border-dark-600 mb-8" />

        {/* Footer bottom */}
        <motion.div
          initial={{ opacity: 0 }}
          whileInView={{ opacity: 1 }}
          viewport={{ once: true }}
          transition={{ duration: 0.6, delay: 0.15 }}
          className="flex flex-col md:flex-row items-center justify-between gap-4 text-xs text-gray-500"
        >
          {/* Left: brand + copyright */}
          <div className="flex items-center gap-2">
            <span className="text-gray-400 font-semibold">Meme Detector</span>
            <span>&copy; {new Date().getFullYear()}</span>
          </div>

          {/* Center: legal links */}
          <div className="flex items-center gap-4">
            <a
              href="https://www.memedetector.es/legal"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors duration-200"
            >
              Legal
            </a>
            <span className="text-dark-600">|</span>
            <a
              href="https://www.memedetector.es/privacidad"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors duration-200"
            >
              Privacidad
            </a>
          </div>

          {/* Right: contact */}
          <div className="flex items-center gap-3">
            <a
              href="mailto:info@memedetector.es"
              className="hover:text-primary transition-colors duration-200"
            >
              info@memedetector.es
            </a>
            <span className="text-dark-600">&middot;</span>
            <a
              href="https://t.me/Ull_trading_bot"
              target="_blank"
              rel="noopener noreferrer"
              className="hover:text-primary transition-colors duration-200"
            >
              Telegram: @Ull_trading_bot
            </a>
          </div>
        </motion.div>
      </div>
    </footer>
  );
}
