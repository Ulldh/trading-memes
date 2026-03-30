import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { MotionConfig } from "framer-motion";
import "./globals.css";

export const metadata: Metadata = {
  title: "Meme Detector \u2014 Detecta las pr\u00f3ximas gems 10x en memecoins",
  description:
    "Machine Learning analiza +5,000 memecoins diariamente en Solana, Ethereum y Base para detectar las pr\u00f3ximas gems antes que nadie.",
  keywords: [
    "memecoin",
    "gem detector",
    "crypto",
    "solana",
    "machine learning",
    "trading signals",
  ],
  openGraph: {
    title: "Meme Detector \u2014 Gems 10x en Memecoins",
    description:
      "ML analiza +5,000 memecoins diariamente. Se\u00f1ales de trading con IA.",
    url: "https://memedetector.es",
    siteName: "Meme Detector",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Meme Detector \u2014 Detecta Gems 10x",
    description: "ML analiza +5,000 memecoins diariamente.",
  },
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const locale = await getLocale();
  const messages = await getMessages();

  return (
    <html lang={locale}>
      <body className="antialiased">
        <a href="#main-content" className="sr-only focus:not-sr-only focus:fixed focus:top-2 focus:left-2 focus:z-[100] focus:bg-primary focus:text-dark-900 focus:px-4 focus:py-2 focus:font-bold focus:rounded">
          Skip to main content
        </a>
        <NextIntlClientProvider locale={locale} messages={messages}>
          <MotionConfig reducedMotion="user">
            {children}
          </MotionConfig>
        </NextIntlClientProvider>
      </body>
    </html>
  );
}
