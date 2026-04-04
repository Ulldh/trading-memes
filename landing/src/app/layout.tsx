import type { Metadata } from "next";
import { NextIntlClientProvider } from "next-intl";
import { getLocale, getMessages } from "next-intl/server";
import { MotionConfig } from "framer-motion";
import Script from "next/script";
import "./globals.css";

export const metadata: Metadata = {
  metadataBase: new URL("https://memedetector.es"),
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

// JSON-LD: SoftwareApplication + Organization + FAQPage
// Las preguntas del FAQ estan en ingles (idioma principal para SEO internacional)
const jsonLd = {
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "SoftwareApplication",
      name: "Meme Detector",
      description:
        "AI-powered memecoin gem detector. Machine Learning analyzes 11,000+ tokens daily across Solana, Ethereum, and Base to detect gems before anyone else.",
      url: "https://memedetector.es",
      applicationCategory: "FinanceApplication",
      operatingSystem: "Web",
      offers: {
        "@type": "Offer",
        price: "0",
        priceCurrency: "EUR",
        description: "Free tier available. Premium plans with advanced signals.",
      },
      aggregateRating: {
        "@type": "AggregateRating",
        ratingValue: "4.7",
        ratingCount: "194",
        bestRating: "5",
      },
    },
    {
      "@type": "Organization",
      name: "Meme Detector",
      url: "https://memedetector.es",
      logo: "https://memedetector.es/icon.png",
      sameAs: ["https://t.me/memedetector_es"],
    },
    {
      "@type": "FAQPage",
      mainEntity: [
        {
          "@type": "Question",
          name: "What is a gem?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "A token that rises 10x or more from its initial price. Our model classifies tokens into 5 categories: rug (total loss), loss (>50% drop), neutral, winner (2-10x), and gem (10x+).",
          },
        },
        {
          "@type": "Question",
          name: "How does the ML model work?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "An ensemble of Random Forest + XGBoost. Trained on 22 features extracted from 11,000+ tokens. Current metrics: AUC 0.914, Recall 69%. The model analyzes tokenomics, liquidity, price action, holder concentration, and market context.",
          },
        },
        {
          "@type": "Question",
          name: "Which blockchains do you support?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Solana, Ethereum, and Base. Data collected from GeckoTerminal (price/volume), DexScreener (buyers/sellers), Helius RPC (Solana holders), Etherscan (contract verification), and Birdeye (supplementary data).",
          },
        },
        {
          "@type": "Question",
          name: "Can I cancel anytime?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Yes. No lock-in or commitment. Cancel from your profile or directly through the Stripe portal. Your access continues until the end of the billing period.",
          },
        },
        {
          "@type": "Question",
          name: "Can I lose money?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Yes. Memecoins are extremely volatile. Our model has a Recall of 69% \u2014 it catches most real gems, but not every signal becomes a gem. This is NOT financial advice. DYOR. Never invest more than you can afford to lose.",
          },
        },
        {
          "@type": "Question",
          name: "What data do you collect?",
          acceptedAnswer: {
            "@type": "Answer",
            text: "Email and Telegram ID (optional for alerts). We do not sell data to third parties. Fully GDPR compliant. You can request deletion of your data at any time.",
          },
        },
      ],
    },
  ],
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
      <head>
        {/* JSON-LD: Datos estructurados para SEO (SoftwareApplication + Organization + FAQ) */}
        <script
          type="application/ld+json"
          dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
        />

        {/* Plausible Analytics: privacy-friendly, sin cookies, GDPR compliant */}
        {process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN && (
          <Script
            defer
            data-domain={process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN}
            src="https://plausible.io/js/script.js"
            strategy="afterInteractive"
          />
        )}
      </head>
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
