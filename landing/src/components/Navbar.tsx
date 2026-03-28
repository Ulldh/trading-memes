"use client";

import { useState, useEffect } from "react";

const navLinks = [
  { label: "La Máquina", href: "#pipeline" },
  { label: "Números", href: "#stats" },
  { label: "Backtesting", href: "#backtesting" },
  { label: "Planes", href: "#pricing" },
  { label: "FAQ", href: "#faq" },
];

export default function Navbar() {
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      className={`w-full transition-all duration-300 ${
        scrolled
          ? "bg-dark-900/95 backdrop-blur-md border-b border-dark-600"
          : "bg-dark-900"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <a href="#" className="flex items-center gap-2 shrink-0">
            <span className="text-primary text-lg font-bold tracking-tight">
              💎 MEME DETECTOR
            </span>
          </a>

          {/* Desktop nav links */}
          <div className="hidden md:flex items-center gap-6">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                className="text-xs text-gray-400 hover:text-primary transition-colors uppercase tracking-wider"
              >
                {link.label}
              </a>
            ))}
          </div>

          {/* Desktop CTA buttons */}
          <div className="hidden md:flex items-center gap-3">
            <a
              href="https://app.memedetector.es"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-gray-400 hover:text-white transition-colors uppercase tracking-wider"
            >
              Iniciar sesión
            </a>
            <a
              href="https://app.memedetector.es"
              target="_blank"
              rel="noopener noreferrer"
              className="border border-primary text-primary px-4 py-1.5 text-xs font-semibold uppercase tracking-wider hover:bg-primary hover:text-dark-900 transition-all duration-300"
            >
              Crear cuenta
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            className="md:hidden text-gray-400 hover:text-white"
          >
            <svg className="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
              {menuOpen ? (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              ) : (
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
              )}
            </svg>
          </button>
        </div>

        {/* Mobile menu */}
        {menuOpen && (
          <div className="md:hidden border-t border-dark-600 py-4 space-y-3">
            {navLinks.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMenuOpen(false)}
                className="block text-sm text-gray-400 hover:text-primary transition-colors uppercase tracking-wider"
              >
                {link.label}
              </a>
            ))}
            <div className="pt-3 border-t border-dark-700 flex gap-3">
              <a
                href="https://app.memedetector.es"
                target="_blank"
                rel="noopener noreferrer"
                className="text-sm text-gray-400 hover:text-white"
              >
                Iniciar sesión
              </a>
              <a
                href="https://app.memedetector.es"
                target="_blank"
                rel="noopener noreferrer"
                className="border border-primary text-primary px-4 py-1 text-sm"
              >
                Crear cuenta
              </a>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
