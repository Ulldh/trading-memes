"use client";

import { useEffect, useState } from "react";
import { motion } from "framer-motion";

export default function Hero() {
  const [tokenCount, setTokenCount] = useState(5000);

  useEffect(() => {
    const interval = setInterval(() => {
      setTokenCount((prev) => prev + Math.floor(Math.random() * 3) + 1);
    }, 2000);
    return () => clearInterval(interval);
  }, []);

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
          className="mb-8 text-xs text-dark-600 tracking-widest uppercase"
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
          Detecta{" "}
          <span className="text-primary glow-green">gems</span>
          <br />
          antes que nadie
        </motion.h1>

        {/* Subtitle */}
        <motion.p
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.4 }}
          className="text-lg md:text-xl text-gray-400 mb-10 max-w-2xl mx-auto"
        >
          Machine Learning analiza{" "}
          <span className="text-primary font-semibold">
            {tokenCount.toLocaleString("es-ES")}+
          </span>{" "}
          memecoins diariamente en Solana, Ethereum y Base
        </motion.p>

        {/* Three stats */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.6 }}
          className="flex flex-wrap justify-center gap-8 mb-12 text-sm"
        >
          <div className="border border-dark-600 px-5 py-3">
            <span className="text-primary font-bold text-lg">94</span>
            <span className="text-gray-500 ml-2">features</span>
          </div>
          <div className="border border-dark-600 px-5 py-3">
            <span className="text-primary font-bold text-lg">3</span>
            <span className="text-gray-500 ml-2">blockchains</span>
          </div>
          <div className="border border-dark-600 px-5 py-3">
            <span className="text-primary font-bold text-lg">07:30</span>
            <span className="text-gray-500 ml-2">UTC señales diarias</span>
          </div>
        </motion.div>

        {/* CTA */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.7, delay: 0.8 }}
        >
          <div className="flex gap-4 justify-center flex-wrap">
            <a
              href="https://app.memedetector.es"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block border-2 border-primary text-primary px-8 py-4 text-sm font-semibold tracking-wider uppercase hover:bg-primary hover:text-dark-900 transition-all duration-300"
            >
              Crear cuenta gratis →
            </a>
            <a
              href="https://app.memedetector.es"
              target="_blank"
              rel="noopener noreferrer"
              className="inline-block border-2 border-dark-600 text-gray-400 px-8 py-4 text-sm font-semibold tracking-wider uppercase hover:border-gray-400 hover:text-white transition-all duration-300"
            >
              Iniciar sesión
            </a>
          </div>
        </motion.div>

        {/* Bottom terminal line */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.2 }}
          className="mt-16 text-xs text-dark-600 font-mono"
        >
          <span className="text-gem-green">STATUS:</span> ONLINE &middot;{" "}
          <span className="text-gem-green">MODELO:</span> v12 &middot;{" "}
          <span className="text-gem-green">F1:</span> 0.726 &middot;{" "}
          <span className="text-gem-green">PRECISION:</span> 72.6%
        </motion.div>

        {/* Disclaimer banner */}
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1, delay: 1.5 }}
          className="mt-6 text-[10px] sm:text-xs text-gray-500"
        >
          Herramienta de analisis de datos. No es asesoramiento financiero.{" "}
          <a
            href="/disclaimer"
            className="text-gem-yellow/70 hover:text-gem-yellow underline underline-offset-2 transition-colors"
          >
            Ver disclaimer completo
          </a>
          .
        </motion.div>
      </div>
    </section>
  );
}
