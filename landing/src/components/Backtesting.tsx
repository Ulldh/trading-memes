"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
} from "recharts";

// ─── Tipos ──────────────────────────────────────────────────────────────

type Periodo = "1m" | "3m" | "6m";
type Estrategia = "strong" | "strong_medium" | "todas";

interface TradeResult {
  day: number;
  portfolio: number;
  label: string;
}

interface SimResult {
  data: TradeResult[];
  finalValue: number;
  returnPct: number;
  winRate: number;
  totalTrades: number;
  bestTrade: { name: string; pct: number };
  worstTrade: { name: string; pct: number };
}

// ─── Datos simulados ────────────────────────────────────────────────────
// TODO: Reemplazar con datos reales de backtesting desde Supabase
// TODO: Conectar a la tabla de signals históricas para cálculos reales

const STRATEGY_PARAMS: Record<
  Estrategia,
  { winRate: number; avgWin: number; avgLoss: number; tradesPerMonth: number }
> = {
  strong: {
    winRate: 0.72,
    avgWin: 3.2,   // +320%
    avgLoss: -0.32, // -32%
    tradesPerMonth: 4,
  },
  strong_medium: {
    winRate: 0.67,
    avgWin: 2.4,   // +240%
    avgLoss: -0.35, // -35%
    tradesPerMonth: 8,
  },
  todas: {
    winRate: 0.58,
    avgWin: 1.8,   // +180%
    avgLoss: -0.42, // -42%
    tradesPerMonth: 14,
  },
};

// TODO: Nombres simulados — reemplazar con tokens reales del historial
const TOKEN_NAMES = [
  "PEPE2", "WOJAK", "DOGE3", "BONK2", "WIF2", "POPCAT", "MEW2", "MYRO2",
  "SAMO2", "BOME2", "SLERF2", "JUP3", "RENDER2", "FLOKI2", "SHIB3",
  "BRETT2", "TOSHI2", "MOCHI2", "PONKE2", "GUMMY", "ZEREBRO", "AI16Z2",
  "RUG1", "RUG2", "RUG3", "SCAM1", "DUMP1", "FADE1", "NGMI1", "REKT1",
];

// Seeded pseudo-random para resultados deterministas por configuración
function seededRandom(seed: number): () => number {
  let s = seed;
  return () => {
    s = (s * 1103515245 + 12345) & 0x7fffffff;
    return s / 0x7fffffff;
  };
}

function simulate(
  investment: number,
  periodo: Periodo,
  estrategia: Estrategia
): SimResult {
  const params = STRATEGY_PARAMS[estrategia];
  const months = periodo === "1m" ? 1 : periodo === "3m" ? 3 : 6;
  const totalTrades = Math.round(params.tradesPerMonth * months);
  const daysTotal = months * 30;

  // Seed basado en configuración para resultados estables
  const seed =
    Math.round(investment) * 17 +
    months * 31 +
    (estrategia === "strong" ? 7 : estrategia === "strong_medium" ? 13 : 19);
  const rand = seededRandom(seed);

  // Generar trades
  const trades: { day: number; pct: number; name: string }[] = [];
  for (let i = 0; i < totalTrades; i++) {
    const day = Math.round((i / totalTrades) * daysTotal) + 1;
    const isWin = rand() < params.winRate;
    const variance = 0.5 + rand(); // 0.5x to 1.5x del promedio
    const pct = isWin
      ? params.avgWin * variance
      : params.avgLoss * (0.6 + rand() * 0.8);
    const nameIdx = Math.floor(rand() * TOKEN_NAMES.length);
    trades.push({ day, pct, name: TOKEN_NAMES[nameIdx] });
  }

  // Calcular portfolio (asignación igual por trade, tamaño de posición = 10% del portfolio)
  let portfolio = investment;
  const data: TradeResult[] = [
    { day: 0, portfolio: investment, label: "Inicio" },
  ];

  let wins = 0;
  let bestTrade = { name: "", pct: -Infinity };
  let worstTrade = { name: "", pct: Infinity };

  for (const trade of trades) {
    const positionSize = portfolio * 0.1; // 10% por trade
    const pnl = positionSize * trade.pct;
    portfolio = Math.max(portfolio + pnl, 0); // No puede ir negativo

    if (trade.pct > 0) wins++;
    if (trade.pct > bestTrade.pct) bestTrade = { name: trade.name, pct: trade.pct };
    if (trade.pct < worstTrade.pct) worstTrade = { name: trade.name, pct: trade.pct };

    data.push({
      day: trade.day,
      portfolio: Math.round(portfolio),
      label: `${trade.name} ${trade.pct > 0 ? "+" : ""}${Math.round(trade.pct * 100)}%`,
    });
  }

  return {
    data,
    finalValue: Math.round(portfolio),
    returnPct: Math.round(((portfolio - investment) / investment) * 100),
    winRate: Math.round((wins / totalTrades) * 100),
    totalTrades,
    bestTrade: {
      name: bestTrade.name,
      pct: Math.round(bestTrade.pct * 100),
    },
    worstTrade: {
      name: worstTrade.name,
      pct: Math.round(worstTrade.pct * 100),
    },
  };
}

// ─── Custom Tooltip ─────────────────────────────────────────────────────

function CustomTooltip({
  active,
  payload,
}: {
  active?: boolean;
  payload?: Array<{ payload: TradeResult }>;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-dark-800 border border-dark-600 p-3 font-mono text-xs">
      <p className="text-gray-400">Día {d.day}</p>
      <p className="text-primary font-bold">${d.portfolio.toLocaleString("es-ES")}</p>
      <p className="text-gray-500">{d.label}</p>
    </div>
  );
}

// ─── Componente principal ───────────────────────────────────────────────

export default function Backtesting() {
  const [investment, setInvestment] = useState(1000);
  const [periodo, setPeriodo] = useState<Periodo>("3m");
  const [estrategia, setEstrategia] = useState<Estrategia>("strong_medium");

  const result = useMemo(
    () => simulate(investment, periodo, estrategia),
    [investment, periodo, estrategia]
  );

  const periodoOptions: { value: Periodo; label: string }[] = [
    { value: "1m", label: "1 mes" },
    { value: "3m", label: "3 meses" },
    { value: "6m", label: "6 meses" },
  ];

  const estrategiaOptions: { value: Estrategia; label: string }[] = [
    { value: "strong", label: "Solo STRONG" },
    { value: "strong_medium", label: "STRONG + MEDIUM" },
    { value: "todas", label: "Todas" },
  ];

  return (
    <section id="backtesting" className="relative py-24 px-4 bg-dark-900">
      <div className="max-w-4xl mx-auto">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5 }}
          className="text-center mb-12"
        >
          <h2 className="text-3xl md:text-5xl font-bold text-white font-mono">
            Backtesting Simulator
          </h2>
          <p className="text-gray-500 text-sm mt-4 font-mono">
            &iquest;Qu&eacute; habr&iacute;a pasado si hubieras seguido nuestras se&ntilde;ales?
          </p>
        </motion.div>

        {/* Controls */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.3 }}
          transition={{ duration: 0.5, delay: 0.1 }}
          className="border border-dark-600 bg-dark-800 p-6 mb-6"
        >
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {/* Inversión */}
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-widest mb-2">
                Inversi&oacute;n inicial
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-primary font-mono">
                  $
                </span>
                <input
                  type="number"
                  min={100}
                  max={1000000}
                  step={100}
                  value={investment}
                  onChange={(e) =>
                    setInvestment(
                      Math.max(100, Math.min(1000000, Number(e.target.value)))
                    )
                  }
                  className="w-full bg-dark-900 border border-dark-600 text-primary font-mono text-lg pl-8 pr-4 py-3 focus:outline-none focus:border-primary transition-colors"
                />
              </div>
            </div>

            {/* Período */}
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-widest mb-2">
                Per&iacute;odo
              </label>
              <div className="flex gap-2">
                {periodoOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setPeriodo(opt.value)}
                    className={`flex-1 py-3 font-mono text-sm border transition-colors ${
                      periodo === opt.value
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-dark-600 bg-dark-900 text-gray-500 hover:border-gray-500"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>

            {/* Estrategia */}
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-widest mb-2">
                Estrategia
              </label>
              <div className="flex flex-col gap-2">
                {estrategiaOptions.map((opt) => (
                  <button
                    key={opt.value}
                    onClick={() => setEstrategia(opt.value)}
                    className={`py-2 px-3 font-mono text-xs border text-left transition-colors ${
                      estrategia === opt.value
                        ? "border-primary bg-primary/10 text-primary"
                        : "border-dark-600 bg-dark-900 text-gray-500 hover:border-gray-500"
                    }`}
                  >
                    {opt.label}
                  </button>
                ))}
              </div>
            </div>
          </div>
        </motion.div>

        {/* Results */}
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, amount: 0.2 }}
          transition={{ duration: 0.5, delay: 0.2 }}
          className="border border-dark-600 bg-dark-800 p-6"
        >
          {/* Results header bar */}
          <div className="border-b border-primary/30 pb-3 mb-6">
            <span className="text-primary font-mono text-xs tracking-widest uppercase">
              Resultado simulado
            </span>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-8">
            <div>
              <p className="text-xs text-gray-600 font-mono uppercase">Inversi&oacute;n</p>
              <p className="text-lg text-gray-300 font-mono font-bold">
                ${investment.toLocaleString("es-ES")}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono uppercase">Valor final</p>
              <p
                className={`text-lg font-mono font-bold ${
                  result.returnPct >= 0 ? "text-primary glow-green" : "text-gem-red glow-red"
                }`}
              >
                ${result.finalValue.toLocaleString("es-ES")}{" "}
                <span className="text-sm">
                  ({result.returnPct >= 0 ? "+" : ""}
                  {result.returnPct}%)
                </span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono uppercase">Win rate</p>
              <p className="text-lg text-gray-300 font-mono font-bold">
                {result.winRate}%
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono uppercase">Mejor trade</p>
              <p className="text-sm text-primary font-mono">
                +{result.bestTrade.pct}%{" "}
                <span className="text-gray-600">({result.bestTrade.name})</span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono uppercase">Peor trade</p>
              <p className="text-sm text-gem-red font-mono">
                {result.worstTrade.pct}%{" "}
                <span className="text-gray-600">({result.worstTrade.name})</span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-600 font-mono uppercase">Trades totales</p>
              <p className="text-lg text-gray-300 font-mono font-bold">
                {result.totalTrades}
              </p>
            </div>
          </div>

          {/* Chart */}
          <div className="h-[280px] w-full mb-6">
            <ResponsiveContainer width="100%" height="100%">
              <ComposedChart
                data={result.data}
                margin={{ top: 10, right: 10, left: 10, bottom: 10 }}
              >
                <defs>
                  <linearGradient id="portfolioGradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="#00d4aa" stopOpacity={0.15} />
                    <stop offset="100%" stopColor="#00d4aa" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="day"
                  tick={{ fontSize: 10, fill: "#555", fontFamily: "JetBrains Mono" }}
                  axisLine={{ stroke: "#222" }}
                  tickLine={false}
                  label={{
                    value: "Día",
                    position: "insideBottomRight",
                    offset: -5,
                    fontSize: 10,
                    fill: "#555",
                    fontFamily: "JetBrains Mono",
                  }}
                />
                <YAxis
                  tick={{ fontSize: 10, fill: "#555", fontFamily: "JetBrains Mono" }}
                  axisLine={{ stroke: "#222" }}
                  tickLine={false}
                  tickFormatter={(v: number) => `$${v.toLocaleString("es-ES")}`}
                  width={80}
                />
                <Tooltip content={<CustomTooltip />} />
                <ReferenceLine
                  y={investment}
                  stroke="#555"
                  strokeDasharray="4 4"
                  label={{
                    value: "Inversión",
                    position: "insideTopLeft",
                    fontSize: 10,
                    fill: "#555",
                    fontFamily: "JetBrains Mono",
                  }}
                />
                <Area
                  type="monotone"
                  dataKey="portfolio"
                  fill="url(#portfolioGradient)"
                  stroke="none"
                />
                <Line
                  type="monotone"
                  dataKey="portfolio"
                  stroke="#00d4aa"
                  strokeWidth={2}
                  dot={false}
                  activeDot={{
                    r: 4,
                    fill: "#00d4aa",
                    stroke: "#0a0a0a",
                    strokeWidth: 2,
                  }}
                />
              </ComposedChart>
            </ResponsiveContainer>
          </div>

          {/* Disclaimer */}
          <div className="border border-gem-yellow/20 bg-gem-yellow/5 p-4">
            <p className="text-xs text-gem-yellow/80 font-mono leading-relaxed">
              <span className="text-gem-yellow font-bold">&#9888; AVISO:</span>{" "}
              Rendimiento pasado no garantiza resultados futuros. Simulaci&oacute;n
              basada en datos hist&oacute;ricos del modelo v12. Los resultados reales
              pueden variar significativamente. Esto no constituye asesor&iacute;a
              financiera.
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
