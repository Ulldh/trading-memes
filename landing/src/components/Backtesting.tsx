"use client";

import { useState, useMemo } from "react";
import { motion } from "framer-motion";
import { useTranslations } from "next-intl";
import {
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
  Area,
  ComposedChart,
  Line,
} from "recharts";

// --- Tipos ---

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

// --- Datos simulados ---
// TODO: Reemplazar con datos reales de backtesting desde Supabase
// TODO: Conectar a la tabla de signals historicas para calculos reales

const STRATEGY_PARAMS: Record<
  Estrategia,
  { winRate: number; avgWin: number; avgLoss: number; tradesPerMonth: number }
> = {
  strong: {
    winRate: 0.72,
    avgWin: 3.2,
    avgLoss: -0.32,
    tradesPerMonth: 4,
  },
  strong_medium: {
    winRate: 0.67,
    avgWin: 2.4,
    avgLoss: -0.35,
    tradesPerMonth: 8,
  },
  todas: {
    winRate: 0.58,
    avgWin: 1.8,
    avgLoss: -0.42,
    tradesPerMonth: 14,
  },
};

// Nombres de tokens para la simulación (neutrales, no obviamente falsos)
const TOKEN_NAMES = [
  "PEPE2", "WOJAK", "DOGE3", "BONK2", "WIF2", "POPCAT", "MEW2", "MYRO2",
  "SAMO2", "BOME2", "SLERF2", "JUP3", "RENDER2", "FLOKI2", "SHIB3",
  "BRETT2", "TOSHI2", "MOCHI2", "PONKE2", "GUMMY", "ZEREBRO", "AI16Z2",
  "FOMO", "ALPHA", "BETA", "DELTA", "SIGMA", "OMEGA", "GAMMA", "KAPPA",
];

// Seeded pseudo-random para resultados deterministas por configuracion
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
  estrategia: Estrategia,
  startLabel: string
): SimResult {
  const params = STRATEGY_PARAMS[estrategia];
  const months = periodo === "1m" ? 1 : periodo === "3m" ? 3 : 6;
  const totalTrades = Math.round(params.tradesPerMonth * months);
  const daysTotal = months * 30;

  // Seed basado en configuracion para resultados estables
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
    const variance = 0.5 + rand();
    const pct = isWin
      ? params.avgWin * variance
      : params.avgLoss * (0.6 + rand() * 0.8);
    const nameIdx = Math.floor(rand() * TOKEN_NAMES.length);
    trades.push({ day, pct, name: TOKEN_NAMES[nameIdx] });
  }

  // Calcular portfolio (asignacion igual por trade, tamano de posicion = 10% del portfolio)
  let portfolio = investment;
  const data: TradeResult[] = [
    { day: 0, portfolio: investment, label: startLabel },
  ];

  let wins = 0;
  let bestTrade = { name: "", pct: -Infinity };
  let worstTrade = { name: "", pct: Infinity };

  for (const trade of trades) {
    const positionSize = portfolio * 0.1;
    const pnl = positionSize * trade.pct;
    portfolio = Math.max(portfolio + pnl, 0);

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

// --- Custom Tooltip ---

function CustomTooltip({
  active,
  payload,
  tooltipDay,
}: {
  active?: boolean;
  payload?: Array<{ payload: TradeResult }>;
  tooltipDay: string;
}) {
  if (!active || !payload?.length) return null;
  const d = payload[0].payload;
  return (
    <div className="bg-dark-800 border border-dark-600 p-3 font-mono text-xs">
      <p className="text-gray-400">{tooltipDay} {d.day}</p>
      <p className="text-primary font-bold">${d.portfolio.toLocaleString("es-ES")}</p>
      <p className="text-gray-500">{d.label}</p>
    </div>
  );
}

// --- Componente principal ---

export default function Backtesting() {
  const t = useTranslations("backtesting");
  const [investment, setInvestment] = useState(1000);
  const [periodo, setPeriodo] = useState<Periodo>("3m");
  const [estrategia, setEstrategia] = useState<Estrategia>("strong_medium");

  const result = useMemo(
    () => simulate(investment, periodo, estrategia, t("start_label")),
    [investment, periodo, estrategia, t]
  );

  const periodoOptions: { value: Periodo; label: string }[] = [
    { value: "1m", label: t("period_options.1m") },
    { value: "3m", label: t("period_options.3m") },
    { value: "6m", label: t("period_options.6m") },
  ];

  const estrategiaOptions: { value: Estrategia; label: string }[] = [
    { value: "strong", label: t("strategy_options.strong") },
    { value: "strong_medium", label: t("strategy_options.strong_medium") },
    { value: "todas", label: t("strategy_options.all") },
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
          <h2 className="text-3xl md:text-5xl font-bold text-white font-mono inline-flex items-center justify-center gap-3 flex-wrap">
            {t("section_title")}
            <span className="text-xs font-bold tracking-widest uppercase bg-gem-yellow/20 text-gem-yellow border border-gem-yellow/40 px-2 py-1 rounded">
              {t("simulation_badge")}
            </span>
          </h2>
          <p className="text-primary/80 text-sm mt-4 font-mono font-semibold">
            {t("section_subtitle")}
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
            {/* Inversion */}
            <div>
              <label htmlFor="backtesting-investment" className="block text-xs text-gray-500 font-mono uppercase tracking-widest mb-2">
                {t("investment_label")}
              </label>
              <div className="relative">
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-primary font-mono">
                  $
                </span>
                <input
                  id="backtesting-investment"
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
                  className="w-full bg-dark-900 border border-dark-600 text-primary font-mono text-lg pl-8 pr-4 py-3 focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-dark-900 transition-colors"
                />
              </div>
            </div>

            {/* Periodo */}
            <div>
              <label className="block text-xs text-gray-500 font-mono uppercase tracking-widest mb-2">
                {t("period_label")}
              </label>
              <div className="flex gap-2" role="radiogroup" aria-label="Período de simulación">
                {periodoOptions.map((opt) => (
                  <button
                    key={opt.value}
                    role="radio"
                    aria-checked={periodo === opt.value}
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
                {t("strategy_label")}
              </label>
              <div className="flex flex-col gap-2" role="radiogroup" aria-label="Estrategia de señales">
                {estrategiaOptions.map((opt) => (
                  <button
                    key={opt.value}
                    role="radio"
                    aria-checked={estrategia === opt.value}
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
              {t("result_header")}
            </span>
          </div>

          {/* Key metrics */}
          <div className="grid grid-cols-2 md:grid-cols-3 gap-6 mb-8">
            <div>
              <p className="text-xs text-gray-400 font-mono uppercase">{t("investment_metric")}</p>
              <p className="text-lg text-gray-300 font-mono font-bold">
                ${investment.toLocaleString("es-ES")}
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400 font-mono uppercase">{t("final_value_metric")}</p>
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
              <p className="text-xs text-gray-400 font-mono uppercase">{t("win_rate_metric")}</p>
              <p className="text-lg text-gray-300 font-mono font-bold">
                {result.winRate}%
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400 font-mono uppercase">{t("best_trade_metric")}</p>
              <p className="text-sm text-primary font-mono">
                +{result.bestTrade.pct}%{" "}
                <span className="text-gray-400">({result.bestTrade.name})</span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400 font-mono uppercase">{t("worst_trade_metric")}</p>
              <p className="text-sm text-gem-red font-mono">
                {result.worstTrade.pct}%{" "}
                <span className="text-gray-400">({result.worstTrade.name})</span>
              </p>
            </div>
            <div>
              <p className="text-xs text-gray-400 font-mono uppercase">{t("total_trades_metric")}</p>
              <p className="text-lg text-gray-300 font-mono font-bold">
                {result.totalTrades}
              </p>
            </div>
          </div>

          {/* Nota de transparencia sobre el chart */}
          <div className="border border-primary/20 bg-primary/5 p-4 mb-4">
            <p className="text-[11px] text-primary/70 font-mono leading-relaxed font-semibold">
              {t("transparency_note")}
            </p>
            <p className="text-[11px] text-gray-400 font-mono leading-relaxed mt-1">
              {t("track_record_note")}{" "}
              <a
                href="https://app.memedetector.es/?tab=signals"
                target="_blank"
                rel="noopener noreferrer"
                className="text-primary underline hover:text-primary/80 transition-colors"
              >
                {t("track_record_link")}
              </a>
            </p>
          </div>

          {/* Chart */}
          <div className="h-[280px] w-full mb-6" role="img" aria-label={`Simulación de portfolio: inversión $${investment.toLocaleString("es-ES")}, valor final $${result.finalValue.toLocaleString("es-ES")}, retorno ${result.returnPct >= 0 ? "+" : ""}${result.returnPct}%, win rate ${result.winRate}%`}>
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
                    value: t("chart_x_label"),
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
                <Tooltip content={<CustomTooltip tooltipDay={t("tooltip_day")} />} />
                <ReferenceLine
                  y={investment}
                  stroke="#555"
                  strokeDasharray="4 4"
                  label={{
                    value: t("chart_ref_label"),
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
              <span className="text-gem-yellow font-bold">&#9888; </span>
              {t("disclaimer")}
            </p>
          </div>
        </motion.div>
      </div>
    </section>
  );
}
