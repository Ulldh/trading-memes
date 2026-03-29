import { NextResponse } from "next/server";

// Forzar ejecucion dinamica en cada request (serverless function)
export const dynamic = "force-dynamic";

// Supabase service_role — solo se ejecuta en server-side
const SUPABASE_URL = process.env.SUPABASE_URL || "https://xayfwuqbbqtyerxzjbec.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

interface ScoreRow {
  token_id: string;
  symbol: string;
  chain: string;
  probability: number;
  signal: string;
}

interface TickerSignal {
  symbol: string;
  chain: string;
  probability: string;
  signal: string;
}

// Cache en memoria (15 min — los scores cambian mas frecuentemente)
let cachedSignals: TickerSignal[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 900 * 1000; // 15 min

// Fallback con datos reales
const FALLBACK_SIGNALS: TickerSignal[] = [
  { symbol: "KIN", chain: "solana", probability: "2.6%", signal: "NONE" },
  { symbol: "EUSX", chain: "solana", probability: "2.1%", signal: "NONE" },
  { symbol: "LIQ", chain: "solana", probability: "1.6%", signal: "NONE" },
  { symbol: "ZKP", chain: "solana", probability: "1.5%", signal: "NONE" },
  { symbol: "SKR", chain: "solana", probability: "1.5%", signal: "NONE" },
  { symbol: "HOWL", chain: "solana", probability: "1.5%", signal: "NONE" },
  { symbol: "KAMA", chain: "solana", probability: "1.4%", signal: "NONE" },
  { symbol: "A2Z", chain: "ethereum", probability: "1.4%", signal: "NONE" },
];

function formatProbability(p: number): string {
  return `${(p * 100).toFixed(1)}%`;
}

function chainIcon(chain: string): string {
  switch (chain) {
    case "solana": return "SOL";
    case "ethereum": return "ETH";
    case "base": return "BASE";
    default: return chain.toUpperCase();
  }
}

export async function GET() {
  const now = Date.now();

  if (cachedSignals && now - cacheTimestamp < CACHE_TTL) {
    return NextResponse.json(cachedSignals, {
      headers: { "Cache-Control": "public, s-maxage=900, stale-while-revalidate=300" },
    });
  }

  try {
    const res = await fetch(`${SUPABASE_URL}/rest/v1/rpc/exec_query`, {
      method: "POST",
      headers: {
        apikey: SUPABASE_KEY,
        Authorization: `Bearer ${SUPABASE_KEY}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        query_text: `SELECT s.token_id, t.symbol, t.chain, s.probability, s.signal
          FROM scores s
          JOIN tokens t ON s.token_id = t.token_id
          WHERE t.symbol IS NOT NULL AND t.symbol != ''
          ORDER BY s.probability DESC
          LIMIT 15`,
      }),
    });

    if (!res.ok) {
      throw new Error(`Supabase responded with ${res.status}`);
    }

    const data: ScoreRow[] = await res.json();

    const signals: TickerSignal[] = data.map((row) => ({
      symbol: row.symbol,
      chain: chainIcon(row.chain),
      probability: formatProbability(row.probability),
      signal: row.signal,
    }));

    cachedSignals = signals;
    cacheTimestamp = now;

    return NextResponse.json(signals, {
      headers: { "Cache-Control": "public, s-maxage=900, stale-while-revalidate=300" },
    });
  } catch {
    return NextResponse.json(FALLBACK_SIGNALS, {
      headers: { "Cache-Control": "public, s-maxage=300" },
    });
  }
}
