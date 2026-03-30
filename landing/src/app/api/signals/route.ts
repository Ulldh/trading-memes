import { NextResponse } from "next/server";
import { z } from "zod";

// Forzar ejecucion dinamica en cada request (serverless function)
export const dynamic = "force-dynamic";

// Supabase service_role — solo se ejecuta en server-side (env vars requeridas)
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Zod schema para validar datos externos de Supabase
const ScoreRowSchema = z.object({
  token_id: z.string().trim(),
  symbol: z.string().trim(),
  chain: z.string().trim(),
  probability: z.number(),
  signal: z.string().trim(),
  price_change: z.number().nullable(),
});

type ScoreRow = z.infer<typeof ScoreRowSchema>;

interface TickerSignal {
  symbol: string;
  chain: string;
  probability: string;
  signal: string;
  priceChange: number | null;
}

// Cache en memoria (15 min — los scores cambian mas frecuentemente)
let cachedSignals: TickerSignal[] | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 900 * 1000; // 15 min

// Fallback con datos reales
const FALLBACK_SIGNALS: TickerSignal[] = [
  { symbol: "KIN", chain: "solana", probability: "2.6%", signal: "NONE", priceChange: 5.2 },
  { symbol: "EUSX", chain: "solana", probability: "2.1%", signal: "NONE", priceChange: -3.1 },
  { symbol: "LIQ", chain: "solana", probability: "1.6%", signal: "NONE", priceChange: 12.4 },
  { symbol: "ZKP", chain: "solana", probability: "1.5%", signal: "NONE", priceChange: -7.8 },
  { symbol: "SKR", chain: "solana", probability: "1.5%", signal: "NONE", priceChange: 1.9 },
  { symbol: "HOWL", chain: "solana", probability: "1.5%", signal: "NONE", priceChange: -0.5 },
  { symbol: "KAMA", chain: "solana", probability: "1.4%", signal: "NONE", priceChange: 8.3 },
  { symbol: "A2Z", chain: "ethereum", probability: "1.4%", signal: "NONE", priceChange: -2.6 },
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

export async function GET(): Promise<NextResponse> {
  const now = Date.now();

  if (cachedSignals && now - cacheTimestamp < CACHE_TTL) {
    return NextResponse.json(cachedSignals, {
      headers: { "Cache-Control": "public, s-maxage=900, stale-while-revalidate=300" },
    });
  }

  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return NextResponse.json(FALLBACK_SIGNALS, {
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
        query_text: `SELECT s.token_id, t.symbol, t.chain, s.probability, s.signal,
          (SELECT CASE WHEN o2.open > 0 THEN ((o2.close - o2.open) / o2.open) * 100 ELSE NULL END
           FROM ohlcv o2
           WHERE o2.token_id = s.token_id AND o2.timeframe = 'day'
           ORDER BY o2.timestamp DESC LIMIT 1) AS price_change
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

    const raw: unknown = await res.json();
    const result = z.array(ScoreRowSchema).safeParse(raw);

    if (!result.success) {
      console.warn("Zod validation failed for Supabase scores:", JSON.stringify(result.error.issues));
      return NextResponse.json(FALLBACK_SIGNALS, {
        headers: { "Cache-Control": "public, s-maxage=300" },
      });
    }

    const data: ScoreRow[] = result.data;

    const signals: TickerSignal[] = data.map((row) => ({
      symbol: row.symbol,
      chain: chainIcon(row.chain),
      probability: formatProbability(row.probability),
      signal: row.signal,
      priceChange: row.price_change != null ? Math.round(row.price_change * 10) / 10 : null,
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
