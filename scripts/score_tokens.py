#!/usr/bin/env python3
"""
score_tokens.py - Califica tokens con modelos ML despues de la recoleccion diaria.

Flujo:
  1. Descarga modelos desde Supabase Storage (si no existen localmente).
  2. Inicializa GemScorer con el modelo descargado.
  3. Califica todos los tokens nuevos (sin label, con OHLCV suficiente).
  4. Guarda senales en CSV local y muestra resumen.

Manejo de errores:
  - Si no hay modelos en Supabase Storage: warning y exit 0 (no falla el workflow).
  - Si no hay tokens nuevos para calificar: info y exit 0.
  - Solo falla (exit 1) por errores inesperados de infraestructura.

Uso:
    python scripts/score_tokens.py
    python scripts/score_tokens.py --model xgboost
    python scripts/score_tokens.py --min-days 3
"""

import argparse
import sys
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)


def main(model_name: str = "random_forest", min_ohlcv_days: int = 7) -> int:
    """
    Ejecuta el pipeline completo de scoring.

    Args:
        model_name: Nombre del modelo a usar ('random_forest' o 'xgboost').
        min_ohlcv_days: Minimo de dias de OHLCV para considerar un token.

    Returns:
        0 si todo OK o modelos no disponibles (skip graceful).
        1 si hay error inesperado.
    """
    # ================================================================
    # Paso 1: Descargar modelos desde Supabase Storage
    # ================================================================
    logger.info("=" * 60)
    logger.info("SCORING DE TOKENS - Pipeline diario")
    logger.info("=" * 60)

    logger.info("\n[1/3] Verificando modelos locales / descargando de Supabase...")

    try:
        from scripts.download_models import download_all
        from config import MODELS_DIR
    except ImportError:
        # Fallback si config no esta disponible
        MODELS_DIR = Path("data/models")
        from scripts.download_models import download_all

    # Verificar si ya hay modelos locales
    model_file = MODELS_DIR / f"{model_name}.joblib"
    if model_file.exists():
        logger.info(f"Modelo local encontrado: {model_file}")
    else:
        logger.info("Modelos no encontrados localmente, descargando de Supabase Storage...")
        try:
            stats = download_all()
            if not stats.get("downloaded"):
                logger.warning(
                    "No se descargaron modelos de Supabase Storage. "
                    "Probablemente no se ha entrenado ningun modelo todavia. "
                    "Saltando scoring."
                )
                return 0
            logger.info(f"Modelos descargados: version {stats.get('version', '?')}")
        except Exception as e:
            logger.warning(
                f"No se pudieron descargar modelos: {e}. "
                "Saltando scoring (primera ejecucion o modelos no disponibles)."
            )
            return 0

    # ================================================================
    # Paso 2: Inicializar scorer y calificar tokens
    # ================================================================
    logger.info(f"\n[2/3] Inicializando GemScorer (modelo={model_name})...")

    try:
        from src.models.scorer import GemScorer
    except ImportError as e:
        logger.error(f"No se pudo importar GemScorer: {e}")
        return 1

    try:
        scorer = GemScorer(model_name=model_name)
    except FileNotFoundError as e:
        logger.warning(
            f"Modelo no disponible: {e}. "
            "Saltando scoring hasta que se entrene un modelo."
        )
        return 0
    except Exception as e:
        logger.error(f"Error inicializando GemScorer: {e}")
        return 1

    logger.info("Calificando tokens nuevos...")
    try:
        results_df = scorer.score_all_new(min_ohlcv_days=min_ohlcv_days)
    except Exception as e:
        logger.error(f"Error durante scoring: {e}")
        return 1

    if results_df.empty:
        logger.info("No hay tokens nuevos para calificar. Pipeline completado.")
        return 0

    # ================================================================
    # Paso 3: Guardar resultados y mostrar resumen
    # ================================================================
    logger.info(f"\n[3/3] Guardando senales ({len(results_df)} tokens)...")

    try:
        output_path = scorer.save_signals(results_df)
        logger.info(f"Senales guardadas en: {output_path}")
    except Exception as e:
        logger.warning(f"Error guardando senales a CSV: {e}")
        # No fatal: los resultados ya se mostraron en logs

    # Resumen final
    logger.info("\n" + "=" * 60)
    logger.info("RESUMEN DE SCORING")
    logger.info("=" * 60)
    logger.info(f"  Modelo:       {model_name}")
    logger.info(f"  Tokens evaluados: {len(results_df)}")

    for signal in ["STRONG", "MEDIUM", "WEAK", "NONE"]:
        count = (results_df["signal"] == signal).sum()
        if count > 0:
            logger.info(f"  Senal {signal}: {count} tokens")

    # Mostrar top candidates (STRONG + MEDIUM)
    top = results_df[results_df["signal"].isin(["STRONG", "MEDIUM"])]
    if not top.empty:
        logger.info(f"\n  Top {len(top)} candidates:")
        for _, row in top.head(10).iterrows():
            symbol = row.get("symbol", "???")
            chain = row.get("chain", "?")
            prob = row.get("probability", 0)
            signal = row.get("signal", "?")
            logger.info(f"    {symbol} ({chain}): {prob:.1%} [{signal}]")

    logger.info("=" * 60)
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Califica tokens con modelos ML despues de la recoleccion diaria"
    )
    parser.add_argument(
        "--model", type=str, default="random_forest",
        choices=["random_forest", "xgboost"],
        help="Modelo a usar para scoring (default: random_forest)"
    )
    parser.add_argument(
        "--min-days", type=int, default=7,
        help="Minimo de dias de OHLCV para considerar un token (default: 7)"
    )

    args = parser.parse_args()
    exit_code = main(model_name=args.model, min_ohlcv_days=args.min_days)
    sys.exit(exit_code)
