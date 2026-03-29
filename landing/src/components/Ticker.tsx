"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";

interface TickerSignal {
  symbol: string;
  chain: string;
  probability: string;
  signal: string;
}

// Fallback mientras carga o si falla la API
const FALLBACK_SIGNALS: TickerSignal[] = [
  { symbol: "KIN", chain: "SOL", probability: "2.6%", signal: "NONE" },
  { symbol: "EUSX", chain: "SOL", probability: "2.1%", signal: "NONE" },
  { symbol: "LIQ", chain: "SOL", probability: "1.6%", signal: "NONE" },
  { symbol: "ZKP", chain: "SOL", probability: "1.5%", signal: "NONE" },
  { symbol: "SKR", chain: "SOL", probability: "1.5%", signal: "NONE" },
  { symbol: "HOWL", chain: "SOL", probability: "1.5%", signal: "NONE" },
  { symbol: "KAMA", chain: "SOL", probability: "1.4%", signal: "NONE" },
  { symbol: "A2Z", chain: "ETH", probability: "1.4%", signal: "NONE" },
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

function SignalItem({ signal }: { signal: TickerSignal }) {
  return (
    <span className="inline-flex items-center mx-6 whitespace-nowrap">
      <span className={`text-[9px] font-mono mr-1.5 ${chainBadgeColor(signal.chain)}`}>
        {signal.chain}
      </span>
      <span className="text-gray-400 font-semibold">{signal.symbol}</span>
      <span className={`ml-1.5 font-bold ${signalColor(signal.signal)}`}>
        {signal.probability}
      </span>
      {signal.signal !== "NONE" && (
        <span className={`ml-1 text-[9px] font-mono ${signalColor(signal.signal)}`}>
          {signal.signal}
        </span>
      )}
    </span>
  );
}

export default function Ticker() {
  const t = useTranslations("ticker");
  const [signals, setSignals] = useState<TickerSignal[]>(FALLBACK_SIGNALS);
  const [isLive, setIsLive] = useState(false);

  useEffect(() => {
    fetch("/api/signals")
      .then((r) => r.json())
      .then((data: TickerSignal[]) => {
        if (Array.isArray(data) && data.length > 0) {
          setSignals(data);
          setIsLive(true);
        }
      })
      .catch(() => {
        // Mantener fallback
      });
  }, []);

  const statusLabel = isLive ? t("live_label") : t("demo_label");

  return (
    <div className="relative w-full bg-dark-800 border-b border-dark-600 overflow-hidden">
      {/* Status indicator */}
      <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center bg-dark-800 pl-3 pr-4 border-r border-dark-600">
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

      {/* Scrolling ticker */}
      <div className="py-2.5 pl-20">
        <div className="animate-ticker inline-flex text-xs">
          {/* Duplicamos para loop infinito */}
          {signals.map((s, i) => (
            <SignalItem key={`a-${i}`} signal={s} />
          ))}
          {signals.map((s, i) => (
            <SignalItem key={`b-${i}`} signal={s} />
          ))}
        </div>
      </div>

      {/* Fade edges */}
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-dark-800 to-transparent pointer-events-none" />
    </div>
  );
}
