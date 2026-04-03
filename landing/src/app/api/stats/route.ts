import { NextResponse } from "next/server";

// Forzar ejecucion dinamica en cada request (serverless function)
export const dynamic = "force-dynamic";

// Supabase service_role — solo se ejecuta en server-side (nunca llega al cliente)
const SUPABASE_URL = process.env.SUPABASE_URL;
const SUPABASE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;

// Forma completa de las stats que devuelve esta API
interface StatsResponse {
  // Conteos de la base de datos
  tokens: number;
  ohlcv: number;
  scores: number;
  gems: number;
  signals: number;

  // Métricas del modelo
  model_version: string;
  features_count: number;
  auc: number;
  recall: number;
  hit_rate: number;
  win_rate: number;
  median_peak: number;

  // Metadata
  last_updated: string;
}

// Cache en memoria para evitar queries excesivas (1 hora)
let cachedStats: StatsResponse | null = null;
let cacheTimestamp = 0;
const CACHE_TTL = 3600 * 1000; // 1 hora en ms

// Fallback con datos reales conocidos (actualizados 2026-04-03)
const FALLBACK_STATS: StatsResponse = {
  tokens: 11350,
  ohlcv: 175000,
  scores: 4305,
  gems: 260,
  signals: 520,

  model_version: "v23",
  features_count: 22,
  auc: 0.914,
  recall: 0.69,
  hit_rate: 0.52,
  win_rate: 0.71,
  median_peak: 3.71,

  last_updated: new Date().toISOString(),
};

// Métricas del modelo que vienen de env vars o metadata
// Se leen de variables de entorno configuradas en Vercel
function getModelMetrics() {
  return {
    model_version: process.env.MODEL_VERSION ?? "v23",
    features_count: Number(process.env.MODEL_FEATURES_COUNT ?? "22"),
    auc: Number(process.env.MODEL_AUC ?? "0.914"),
    recall: Number(process.env.MODEL_RECALL ?? "0.69"),
    hit_rate: Number(process.env.MODEL_HIT_RATE ?? "0.52"),
    win_rate: Number(process.env.MODEL_WIN_RATE ?? "0.71"),
    median_peak: Number(process.env.MODEL_MEDIAN_PEAK ?? "3.71"),
  };
}

export async function GET() {
  const now = Date.now();

  // Devolver cache si es valido
  if (cachedStats && now - cacheTimestamp < CACHE_TTL) {
    return NextResponse.json(cachedStats, {
      headers: { "Cache-Control": "public, s-maxage=3600, stale-while-revalidate=1800" },
    });
  }

  // Sin credenciales de Supabase, devolver fallback
  if (!SUPABASE_URL || !SUPABASE_KEY) {
    return NextResponse.json(FALLBACK_STATS, {
      headers: { "Cache-Control": "public, s-maxage=300" },
    });
  }

  try {
    // Query ampliada: conteos de todas las tablas relevantes
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
          (SELECT COUNT(*) FROM labels WHERE label_binary = 1) as gems,
          (SELECT COUNT(*) FROM scores WHERE signal IN ('STRONG', 'MEDIUM')) as signals`,
      }),
    });

    if (!res.ok) {
      throw new Error(`Supabase responded with ${res.status}`);
    }

    const data = await res.json();
    const row = data?.[0];

    if (!row) {
      throw new Error("Empty response from Supabase");
    }

    // Combinar conteos de DB con métricas del modelo
    const modelMetrics = getModelMetrics();

    const stats: StatsResponse = {
      tokens: Number(row.tokens) || FALLBACK_STATS.tokens,
      ohlcv: Number(row.ohlcv) || FALLBACK_STATS.ohlcv,
      scores: Number(row.scores) || FALLBACK_STATS.scores,
      gems: Number(row.gems) || FALLBACK_STATS.gems,
      signals: Number(row.signals) || FALLBACK_STATS.signals,
      ...modelMetrics,
      last_updated: new Date().toISOString(),
    };

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
