"""
daily_narrative.py — Genera un resumen diario del mercado de memecoins.

Analiza los datos del dia desde Supabase y genera un resumen corto
en texto natural (basado en plantillas, sin LLM) que se guarda en la
tabla 'narratives' para mostrarse en el dashboard.

El resumen incluye:
  - Tokens nuevos descubiertos hoy
  - Senales STRONG y MEDIUM detectadas
  - Top token por probabilidad
  - Distribucion por cadena
  - Gems recientes (si hay)

Uso:
    python scripts/daily_narrative.py

Se ejecuta automaticamente al final del pipeline diario (daily-collect.yml).
"""

import sys
import random
from datetime import datetime, timezone

# Asegurar que el directorio raiz esta en el path
sys.path.insert(0, ".")

from src.data.supabase_storage import get_storage
from src.utils.logger import get_logger

logger = get_logger(__name__)

# =============================================================================
# Plantillas de narrativa — variadas para que no suene repetitivo
# =============================================================================

# Intro: cuantos tokens se analizaron
_INTRO_TEMPLATES = [
    "Hoy se analizaron {total} tokens nuevos en {chains} cadenas.",
    "El escaner detecto {total} tokens frescos distribuidos en {chains} blockchains.",
    "Jornada con {total} tokens nuevos incorporados al seguimiento.",
    "Se incorporaron {total} memecoins al radar en las ultimas 24 horas.",
]

# Senales detectadas
_SIGNALS_TEMPLATES = [
    "{strong} senales STRONG y {medium} MEDIUM detectadas por el modelo.",
    "El modelo identifico {strong} oportunidades de alta confianza y {medium} de confianza media.",
    "Detectadas {strong} senales STRONG + {medium} MEDIUM en el analisis de hoy.",
    "Hoy hay {strong} senales de alta probabilidad y {medium} de probabilidad media activas.",
]

# Sin senales
_NO_SIGNALS_TEMPLATES = [
    "Sin senales STRONG hoy — el modelo no encontro oportunidades claras.",
    "Jornada tranquila: el modelo no detecto senales de alta confianza.",
    "Hoy no se generaron senales STRONG. El mercado esta en espera.",
]

# Top token
_TOP_TEMPLATES = [
    "Top del dia: {symbol} con {prob}% de probabilidad en {chain}.",
    "El token con mayor score es {symbol} ({prob}%) en {chain}.",
    "Mejor candidato: {symbol} con un score de {prob}% ({chain}).",
]

# Distribucion de cadenas
_CHAIN_TEMPLATES = [
    "{dominant} lidera con {pct}% de los tokens nuevos.",
    "{dominant} domina el mercado con {pct}% de las nuevas incorporaciones.",
    "La mayoria de tokens nuevos ({pct}%) estan en {dominant}.",
]

# Gems recientes
_GEM_TEMPLATES = [
    "Se confirmo {count} nuevo gem (10x+) en las ultimas 48h.",
    "{count} gems confirmados recientemente — el modelo sigue encontrando oportunidades.",
]

# Cuando no hay tokens nuevos
_EMPTY_TEMPLATE = (
    "Sin tokens nuevos hoy. El pipeline continua monitoreando "
    "{total_tracked} tokens existentes."
)


def _pick(templates: list) -> str:
    """Selecciona una plantilla aleatoria de la lista."""
    return random.choice(templates)


def generate_narrative() -> tuple[str, dict]:
    """Genera la narrativa del dia consultando datos de Supabase.

    Returns:
        Tupla (texto_narrativa, dict_stats) donde stats contiene
        los datos crudos usados para generar la narrativa.
    """
    storage = get_storage()
    stats = {}

    # --- 1. Tokens nuevos hoy ---
    try:
        df_new = storage.query(
            "SELECT chain, COUNT(*) as n FROM tokens "
            "WHERE first_seen >= CURRENT_DATE "
            "GROUP BY chain"
        )
        new_by_chain = {}
        total_new = 0
        if not df_new.empty:
            for _, r in df_new.iterrows():
                chain = r["chain"] or "unknown"
                count = int(r["n"])
                new_by_chain[chain] = count
                total_new += count
    except Exception as e:
        logger.warning(f"Error consultando tokens nuevos: {e}")
        new_by_chain = {}
        total_new = 0

    stats["new_tokens"] = total_new
    stats["new_by_chain"] = new_by_chain

    # --- 2. Total tokens monitoreados ---
    try:
        df_total = storage.query("SELECT COUNT(*) as n FROM tokens")
        total_tracked = int(df_total["n"].iloc[0]) if not df_total.empty else 0
    except Exception:
        total_tracked = 0
    stats["total_tracked"] = total_tracked

    # --- 3. Senales activas hoy ---
    try:
        df_signals = storage.query(
            "SELECT signal, COUNT(*) as n FROM scores "
            "WHERE scored_at >= CURRENT_DATE "
            "GROUP BY signal"
        )
        strong = 0
        medium = 0
        if not df_signals.empty:
            for _, r in df_signals.iterrows():
                if r["signal"] == "STRONG":
                    strong = int(r["n"])
                elif r["signal"] == "MEDIUM":
                    medium = int(r["n"])
    except Exception:
        strong = 0
        medium = 0

    stats["strong"] = strong
    stats["medium"] = medium

    # --- 4. Top token por probabilidad ---
    try:
        df_top = storage.query(
            "SELECT s.probability, t.symbol, t.chain "
            "FROM scores s JOIN tokens t ON s.token_id = t.token_id "
            "WHERE s.scored_at >= CURRENT_DATE "
            "ORDER BY s.probability DESC LIMIT 1"
        )
        if not df_top.empty:
            top_symbol = df_top["symbol"].iloc[0] or "???"
            top_prob = int(float(df_top["probability"].iloc[0]) * 100)
            top_chain = (df_top["chain"].iloc[0] or "").capitalize()
        else:
            top_symbol = None
            top_prob = 0
            top_chain = ""
    except Exception:
        top_symbol = None
        top_prob = 0
        top_chain = ""

    stats["top_symbol"] = top_symbol
    stats["top_prob"] = top_prob
    stats["top_chain"] = top_chain

    # --- 5. Gems recientes (ultimas 48h) ---
    try:
        df_gems = storage.query(
            "SELECT COUNT(*) as n FROM labels "
            "WHERE label_binary = 1 "
            "AND labeled_at >= CURRENT_DATE - INTERVAL '2 days'"
        )
        recent_gems = int(df_gems["n"].iloc[0]) if not df_gems.empty else 0
    except Exception:
        recent_gems = 0
    stats["recent_gems"] = recent_gems

    # --- Construir narrativa ---
    parts = []

    if total_new == 0:
        # Sin tokens nuevos — narrativa corta
        parts.append(_EMPTY_TEMPLATE.format(total_tracked=f"{total_tracked:,}"))
        if strong > 0 or medium > 0:
            parts.append(
                _pick(_SIGNALS_TEMPLATES).format(strong=strong, medium=medium)
            )
    else:
        # Intro con total de tokens nuevos
        n_chains = len(new_by_chain)
        parts.append(
            _pick(_INTRO_TEMPLATES).format(total=total_new, chains=n_chains)
        )

        # Senales
        if strong > 0 or medium > 0:
            parts.append(
                _pick(_SIGNALS_TEMPLATES).format(strong=strong, medium=medium)
            )
        else:
            parts.append(_pick(_NO_SIGNALS_TEMPLATES))

        # Top token
        if top_symbol and top_prob > 0:
            parts.append(
                _pick(_TOP_TEMPLATES).format(
                    symbol=top_symbol, prob=top_prob, chain=top_chain
                )
            )

        # Distribucion por cadena (si hay 2+ cadenas)
        if len(new_by_chain) >= 2:
            dominant_chain = max(new_by_chain, key=new_by_chain.get)
            dominant_pct = int(new_by_chain[dominant_chain] / total_new * 100)
            if dominant_pct > 50:
                parts.append(
                    _pick(_CHAIN_TEMPLATES).format(
                        dominant=dominant_chain.capitalize(), pct=dominant_pct
                    )
                )

    # Gems recientes
    if recent_gems > 0:
        parts.append(
            _pick(_GEM_TEMPLATES).format(count=recent_gems)
        )

    # Limitar a 4 frases max
    narrative = " ".join(parts[:4])

    return narrative, stats


def save_narrative(narrative: str, stats: dict) -> bool:
    """Guarda la narrativa del dia en Supabase (tabla narratives).

    Usa UPSERT por fecha — si ya existe narrativa para hoy, la reemplaza.

    Args:
        narrative: Texto de la narrativa.
        stats: Dict con estadisticas usadas para generar la narrativa.

    Returns:
        True si se guardo correctamente.
    """
    storage = get_storage()
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")

    try:
        # Crear tabla si no existe (self-bootstrapping)
        storage.query(
            """
            CREATE TABLE IF NOT EXISTS narratives (
                id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                date DATE NOT NULL UNIQUE,
                content TEXT NOT NULL,
                stats JSONB DEFAULT '{}',
                created_at TIMESTAMPTZ DEFAULT NOW()
            )
            """
        )
    except Exception as e:
        # La tabla puede existir o la query CREATE puede no estar en allowlist
        logger.debug(f"CREATE TABLE narratives (puede ya existir): {e}")

    # Intentar upsert via PostgREST
    try:
        import json
        client = storage.client
        data = {
            "date": today,
            "content": narrative,
            "stats": json.dumps(stats),
        }
        # Upsert: si ya existe para esta fecha, sobreescribe
        client.table("narratives").upsert(
            data, on_conflict="date"
        ).execute()
        logger.info(f"Narrativa guardada para {today}")
        return True
    except Exception as e:
        logger.error(f"Error guardando narrativa: {e}")
        # Fallback: intentar con SQL directo
        try:
            import json
            storage.query(
                "INSERT INTO narratives (date, content, stats) "
                "VALUES (?, ?, ?) "
                "ON CONFLICT (date) DO UPDATE SET content = EXCLUDED.content, "
                "stats = EXCLUDED.stats",
                (today, narrative, json.dumps(stats))
            )
            logger.info(f"Narrativa guardada via SQL para {today}")
            return True
        except Exception as e2:
            logger.error(f"Error guardando narrativa via SQL: {e2}")
            return False


def main():
    """Punto de entrada: genera y guarda la narrativa del dia."""
    logger.info("=== Generando narrativa diaria ===")

    narrative, stats = generate_narrative()

    logger.info(f"Narrativa generada: {narrative}")
    logger.info(f"Stats: {stats}")

    # Imprimir para visibilidad en CI logs
    print(f"\n{'='*60}")
    print(f"NARRATIVA DEL DIA ({datetime.now(timezone.utc).strftime('%Y-%m-%d')})")
    print(f"{'='*60}")
    print(narrative)
    print(f"{'='*60}")
    print(f"Stats: {stats}")

    success = save_narrative(narrative, stats)
    if success:
        print("Narrativa guardada en Supabase correctamente.")
    else:
        print("ADVERTENCIA: No se pudo guardar la narrativa. Revisar logs.")
        # No fallar el pipeline por esto
        sys.exit(0)


if __name__ == "__main__":
    main()
