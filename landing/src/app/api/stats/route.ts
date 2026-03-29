import { NextResponse } from "next/server";

// Forzar ejecucion dinamica en cada request (serverless function)
export const dynamic = "force-dynamic";

// Supabase service_role — solo se ejecuta en server-side (nunca llega al cliente)
const SUPABASE_URL = process.env.SUPABASE_URL || "https://xayfwuqbbqtyerxzjbec.supabase.co";
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY || "";

// Cache en memoria para evitar queries excesivas (1 hora)
let cachedStats: Record<string, number> | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 3600 * 1000; // 1 hora en ms

// Fallback con datos reales conocidos (actualizados 2026-03-29)
const FALLBACK_STATS = {
  tokens: 5748,
  ohlcv: 134900,
  scores: 1389,
  gems: 140,
};

export async function GET() {
  const now = Date.now();

  // Devolver cache si es valido
  if (cachedStats && now - cacheTimestamp < CACHE_TTL) {
    return NextResponse.json(cachedStats, {
      headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=1800" },
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
        query_text: `SELECT
          (SELECT COUNT(*) FROM tokens) as tokens,
          (SELECT COUNT(*) FROM ohlcv) as ohlcv,
          (SELECT COUNT(*) FROM scores) as scores,
          (SELECT COUNT(*) FROM labels WHERE label_binary = 1) as gems`,
      }),
    });

    if (!res.ok) {
      throw new Error(`Supabase responded with ${res.status}`);
    }

    const data = await res.json();
    const stats = data?.[0] ?? FALLBACK_STATS;

    // Actualizar cache
    cachedStats = stats;
    cacheTimestamp = now;

    return NextResponse.json(stats, {
      headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=1800" },
    });
  } catch {
    // En caso de error, devolver fallback
    return NextResponse.json(FALLBACK_STATS, {
      headers: { "Cache-Control": "public, s-maxage=300" },
    });
  }
}
