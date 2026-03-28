import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Meme Detector — Detecta las próximas gems 10x en memecoins",
  description:
    "Machine Learning analiza +5,000 memecoins diariamente en Solana, Ethereum y Base para detectar las próximas gems antes que nadie.",
  keywords: [
    "memecoin",
    "gem detector",
    "crypto",
    "solana",
    "machine learning",
    "trading signals",
  ],
  openGraph: {
    title: "Meme Detector — Gems 10x en Memecoins",
    description:
      "ML analiza +5,000 memecoins diariamente. Señales de trading con IA.",
    url: "https://memedetector.es",
    siteName: "Meme Detector",
    type: "website",
  },
  twitter: {
    card: "summary_large_image",
    title: "Meme Detector — Detecta Gems 10x",
    description: "ML analiza +5,000 memecoins diariamente.",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="es">
      <body className="antialiased">{children}</body>
    </html>
  );
}
