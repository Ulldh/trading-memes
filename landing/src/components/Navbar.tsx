"use client";

import { useState, useEffect } from "react";
import { useTranslations } from "next-intl";
import LanguageSwitcher from "./LanguageSwitcher";

export default function Navbar() {
  const t = useTranslations("nav");
  const [scrolled, setScrolled] = useState(false);
  const [menuOpen, setMenuOpen] = useState(false);

  const navLinks = [
    { label: t("pipeline"), href: "/#pipeline" },
    { label: t("stats"), href: "/#stats" },
    { label: t("backtesting"), href: "/#backtesting" },
    { label: t("pricing"), href: "/#pricing" },
    { label: t("faq"), href: "/#faq" },
    { label: t("academy"), href: "/academia" },
  ];

  useEffect(() => {
    const handleScroll = () => setScrolled(window.scrollY > 20);
    window.addEventListener("scroll", handleScroll);
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  return (
    <nav
      aria-label="Main navigation"
      className={`w-full transition-all duration-300 ${
        scrolled
          ? "bg-dark-900/95 backdrop-blur-md border-b border-dark-600"
          : "bg-dark-900"
      }`}
    >
      <div className="max-w-7xl mx-auto px-4 sm:px-6">
        <div className="flex items-center justify-between h-14">
          {/* Logo */}
          <a href="/" aria-label="Meme Detector - Inicio" className="flex items-center gap-2 shrink-0">
            <span className="text-primary text-lg font-bold tracking-tight">
              <span aria-hidden="true">{"\u{1F48E}"}</span> {t("brand")}
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

          {/* Desktop CTA buttons + Language Switcher */}
          <div className="hidden md:flex items-center gap-3">
            <LanguageSwitcher />
            <a
              href="https://app.memedetector.es/?tab=login"
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-gray-400 hover:text-white transition-colors uppercase tracking-wider"
            >
              {t("login")}
            </a>
            <a
              href="https://app.memedetector.es/?tab=register"
              target="_blank"
              rel="noopener noreferrer"
              className="border border-primary text-primary px-4 py-1.5 text-xs font-semibold uppercase tracking-wider hover:bg-primary hover:text-dark-900 transition-all duration-300"
            >
              {t("signup")}
            </a>
          </div>

          {/* Mobile hamburger */}
          <button
            onClick={() => setMenuOpen(!menuOpen)}
            aria-label={menuOpen ? "Cerrar menú de navegación" : "Abrir menú de navegación"}
            aria-expanded={menuOpen}
            aria-controls={menuOpen ? "mobile-nav" : undefined}
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
          <div id="mobile-nav" className="md:hidden border-t border-dark-600 py-4 space-y-3">
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
            <div className="pt-3 border-t border-dark-700 space-y-3">
              <div className="flex items-center gap-2">
                <LanguageSwitcher />
              </div>
              <div className="flex gap-3">
                <a
                  href="https://app.memedetector.es/?tab=login"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-gray-400 hover:text-white"
                >
                  {t("login")}
                </a>
                <a
                  href="https://app.memedetector.es/?tab=register"
                  target="_blank"
                  rel="noopener noreferrer"
                  className="border border-primary text-primary px-4 py-1 text-sm"
                >
                  {t("signup")}
                </a>
              </div>
            </div>
          </div>
        )}
      </div>
    </nav>
  );
}
