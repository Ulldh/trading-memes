"use client";

// TODO: Reemplazar datos hardcoded con señales reales de Supabase
const signals = [
  { symbol: "PEPE", change: "+340%", positive: true },
  { symbol: "WIF", change: "+120%", positive: true },
  { symbol: "RUG3", change: "-92%", positive: false },
  { symbol: "BONK", change: "+89%", positive: true },
  { symbol: "SCAM7", change: "-98%", positive: false },
  { symbol: "GEM1", change: "+1.200%", positive: true },
  { symbol: "DOGE2", change: "+45%", positive: true },
  { symbol: "FLOKI", change: "+210%", positive: true },
  { symbol: "RUG9", change: "-87%", positive: false },
  { symbol: "MYRO", change: "+560%", positive: true },
  { symbol: "POPCAT", change: "+180%", positive: true },
  { symbol: "DUMP4", change: "-95%", positive: false },
];

function SignalItem({
  symbol,
  change,
  positive,
}: {
  symbol: string;
  change: string;
  positive: boolean;
}) {
  return (
    <span className="inline-flex items-center mx-6 whitespace-nowrap">
      <span className={positive ? "text-primary" : "text-gem-red"}>
        {positive ? "▲" : "▼"}
      </span>
      <span className="text-gray-400 mx-1.5 font-semibold">{symbol}</span>
      <span
        className={`font-bold ${positive ? "text-primary glow-green" : "text-gem-red glow-red"}`}
      >
        {change}
      </span>
    </span>
  );
}

export default function Ticker() {
  return (
    <div className="relative w-full bg-dark-800 border-b border-dark-600 overflow-hidden">
      {/* LIVE indicator */}
      <div className="absolute left-0 top-0 bottom-0 z-10 flex items-center bg-dark-800 pl-3 pr-4 border-r border-dark-600">
        <span className="pulse-dot inline-block w-2 h-2 bg-gem-red rounded-full mr-2" />
        <span className="text-[10px] text-gem-red font-bold tracking-widest uppercase">
          LIVE
        </span>
      </div>

      {/* Scrolling ticker */}
      <div className="py-2.5 pl-20">
        <div className="animate-ticker inline-flex text-xs">
          {/* Duplicamos para loop infinito */}
          {signals.map((s, i) => (
            <SignalItem key={`a-${i}`} {...s} />
          ))}
          {signals.map((s, i) => (
            <SignalItem key={`b-${i}`} {...s} />
          ))}
        </div>
      </div>

      {/* Fade edges */}
      <div className="absolute right-0 top-0 bottom-0 w-16 bg-gradient-to-l from-dark-800 to-transparent pointer-events-none" />
    </div>
  );
}
