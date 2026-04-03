"use client";

import { useEffect, useState } from "react";

// Forma de los datos que devuelve /api/stats
export interface StatsData {
  // Conteos de la base de datos
  tokens: number;
  ohlcv: number;
  scores: number;
  gems: number;
  signals: number; // señales STRONG + MEDIUM

  // Métricas del modelo (metadata)
  model_version: string;
  features_count: number;
  auc: number;
  recall: number;
  hit_rate: number;  // STRONG gem rate (52%)
  win_rate: number;  // % señales STRONG que alcanzan 2x+ (71%)
  median_peak: number; // mediana peak STRONG (3.71x)

  // Metadata
  last_updated: string;
}

// Fallback con datos reales conocidos (actualizados 2026-04-03)
// Se usan solo si la API no responde
export const FALLBACK_STATS: StatsData = {
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

// Cache en módulo para evitar re-fetch entre componentes
let moduleCache: StatsData | null = null;
let fetchPromise: Promise<StatsData> | null = null;

async function fetchStats(): Promise<StatsData> {
  try {
    const res = await fetch("/api/stats");
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();
    // Validación mínima: si tiene tokens es válido
    if (data && typeof data.tokens === "number") {
      return data as StatsData;
    }
    return FALLBACK_STATS;
  } catch {
    return FALLBACK_STATS;
  }
}

/**
 * Hook compartido para las métricas de la landing.
 * Todos los componentes usan este hook — solo se hace un fetch.
 */
export function useStats(): StatsData {
  const [stats, setStats] = useState<StatsData>(moduleCache ?? FALLBACK_STATS);

  useEffect(() => {
    // Si ya hay cache, usarla directamente
    if (moduleCache) {
      setStats(moduleCache);
      return;
    }

    // Reutilizar la misma promesa si ya se está fetching
    if (!fetchPromise) {
      fetchPromise = fetchStats();
    }

    fetchPromise.then((data) => {
      moduleCache = data;
      setStats(data);
    });
  }, []);

  return stats;
}
