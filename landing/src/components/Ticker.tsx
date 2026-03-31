"use client";

import React, { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { z } from "zod";

// Zod schema para validar respuesta de /api/signals
const TickerSignalSchema = z.object({
  symbol: z.string().trim(),
  chain: z.string().trim(),
  probability: z.string().trim(),
  signal: z.string().trim(),
  priceChange: z.number().nullable(),
});

type TickerSignal = z.infer<typeof TickerSignalSchema>;

// Fallback mientras carga o si falla la API
// Muestra señales STRONG reales-looking de memecoins conocidos de Solana
const FALLBACK_SIGNALS: TickerSignal[] = [
  { symbol: "BONK", chain: "SOL", probability: "89.3%", signal: "STRONG", priceChange: 187.4 },
  { symbol: "WIF", chain: "SOL", probability: "82.7%", signal: "STRONG", priceChange: 94.2 },
  { symbol: "POPCAT", chain: "SOL", probability: "91.1%", signal: "STRONG", priceChange: 263.8 },
  { symbol: "MEW", chain: "SOL", probability: "78.4%", signal: "STRONG", priceChange: 156.9 },
  { symbol: "MYRO", chain: "SOL", probability: "85.6%", signal: "STRONG", priceChange: 73.5 },
  { symbol: "PONKE", chain: "SOL", probability: "76.2%", signal: "STRONG", priceChange: 118.3 },
  { symbol: "BOME", chain: "SOL", probability: "88.9%", signal: "STRONG", priceChange: 312.7 },
  { symbol: "SLERF", chain: "SOL", probability: "79.8%", signal: "STRONG", priceChange: 64.1 },
];

function signalColor(signal: string): string {
  switch (signal) {
    case "STRONG":
      return "text-primary glow-green";
    case "MEDIUM":
      return "text-gem-yellow";
    default:
      return "text-gray-400";
  }
}

function priceChangeColor(change: number | null): string {
  if (change == null || change === 0) return "text-gray-500";
  return change > 0 ? "text-gem-green" : "text-gem-red";
}

function priceChangeText(change: number | null): string {
  if (change == null) return "";
  const sign = change > 0 ? "+" : "";
  return `${sign}${change.toFixed(1)}%`;
}

function priceChangeArrow(change: number | null): string {
  if (change == null || change === 0) return "";
  return change > 0 ? "\u25B2" : "\u25BC";
}

function chainBadgeColor(chain: string): string {
  switch (chain) {
    case "SOL":
      return "text-purple-400";
    case "ETH":
      return "text-blue-400";
    case "BASE":
      return "text-sky-400";
    default:
      return "text-gray-500";
  }
}

function SignalItem({ signal }: { signal: TickerSignal }): React.JSX.Element {
  return (
    <li className="inline-flex items-center mx-6 whitespace-nowrap list-none">
      <span className={`text-[9px] font-mono mr-1.5 ${chainBadgeColor(signal.chain)}`}>
        {signal.chain}
      </span>
      <span className="text-gray-400 font-semibold">{signal.symbol}</span>
      {signal.priceChange != null && (
        <span className={`ml-1.5 text-[10px] font-mono font-bold ${priceChangeColor(signal.priceChange)}`}>
          {priceChangeArrow(signal.priceChange)} {priceChangeText(signal.priceChange)}
        </span>
      )}
      <span className={`ml-1.5 font-bold ${signalColor(signal.signal)}`}>
        {signal.probability}
      </span>
      {signal.signal !== "NONE" && (
        <span className={`ml-1 text-[9px] font-mono ${signalColor(signal.signal)}`}>
          {signal.signal}
        </span>
      )}
    </li>
  );
}

export function Ticker(): React.JSX.Element {
  const t = useTranslations("ticker");
  const [signals, setSignals] = useState<TickerSignal[]>(FALLBACK_SIGNALS);
  const [isLive, setIsLive] = useState(false);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    fetch("/api/signals")
      .then((r) => r.json())
      .then((raw: unknown) => {
        const result = z.array(TickerSignalSchema).safeParse(raw);
        if (result.success && result.data.length > 0) {
          setSignals(result.data);
          setIsLive(true);
        } else if (!result.success) {
          console.warn("Zod validation failed for signals:", JSON.stringify(result.error.issues));
        }
      })
      .catch(() => {
        // Mantener fallback
      });
  }, []);

  const statusLabel = isLive ? t("live_label") : t("demo_label");

  return (
    <div className="relative w-full bg-dark-800 border-b border-dark-600 overflow-hidden" aria-label="Señales de trading en tiempo real">
      {/* Status indicator */}
      <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center bg-dark-800 pl-3 pr-4 border-r border-dark-600" aria-live="polite">
        <span
          className={`inline-block w-2 h-2 rounded-full mr-2 ${
            isLive ? "bg-primary animate-pulse" : "bg-gem-yellow"
          }`}
        />
        <span
          className={`text-[10px] font-bold tracking-widest uppercase ${
            isLive ? "text-primary" : "text-gem-yellow"
          }`}
        >
          {statusLabel}
        </span>
      </div>

      {/* Pause/play button */}
      <button
        onClick={() => setPaused(!paused)}
        aria-label={paused ? "Reanudar ticker" : "Pausar ticker"}
        className="absolute left-[108px] top-0 bottom-0 z-10 shrink-0 px-2 text-gray-500 hover:text-white text-xs"
      >
        {paused ? "\u25B6" : "\u23F8"}
      </button>

      {/* Scrolling ticker */}
      <div className="py-2.5 pl-28" role="region" aria-label={t("live_label")}>
        <ul className="animate-ticker inline-flex text-xs list-none m-0 p-0" style={{ animationPlayState: paused ? 'paused' : 'running' }}>
          {/* Señales originales */}
          {signals.map((s, i) => (
            <SignalItem key={`a-${i}`} signal={s} />
          ))}
          {/* Duplicado para loop infinito */}
          <span aria-hidden="true" className="inline-flex">
            {signals.map((s, i) => (
              <SignalItem key={`b-${i}`} signal={s} />
            ))}
          </span>
        </ul>
      </div>

      {/* Fade edges */}
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-dark-800 to-transparent pointer-events-none" />
    </div>
  );
}
