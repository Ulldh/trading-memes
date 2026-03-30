"use client";

import { useLocale } from "next-intl";

const languages = [
  { code: "es", flag: "\u{1F1EA}\u{1F1F8}", label: "ES" },
  { code: "en", flag: "\u{1F1EC}\u{1F1E7}", label: "EN" },
  { code: "de", flag: "\u{1F1E9}\u{1F1EA}", label: "DE" },
  { code: "pt", flag: "\u{1F1E7}\u{1F1F7}", label: "PT" },
  { code: "fr", flag: "\u{1F1EB}\u{1F1F7}", label: "FR" },
];

export default function LanguageSwitcher() {
  const currentLocale = useLocale();

  const setLanguage = (lang: string) => {
    document.cookie = `locale=${lang};path=/;max-age=31536000`;
    window.location.reload();
  };

  return (
    <div className="flex items-center gap-0.5">
      {languages.map((lang) => (
        <button
          key={lang.code}
          onClick={() => setLanguage(lang.code)}
          aria-label={`Cambiar idioma a ${lang.label}`}
          aria-current={currentLocale === lang.code ? "true" : undefined}
          className={`text-sm min-w-[44px] min-h-[44px] flex items-center justify-center transition-all duration-200 ${
            currentLocale === lang.code
              ? "opacity-100 scale-110"
              : "opacity-50 hover:opacity-100"
          }`}
          title={lang.label}
        >
          <span aria-hidden="true">{lang.flag}</span>
        </button>
      ))}
    </div>
  );
}
