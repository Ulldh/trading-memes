#!/usr/bin/env python3
"""
retrain_pipeline.py - Pipeline completo de re-entrenamiento.

Ejecuta en secuencia:
    1. Re-etiquetar todos los tokens con OHLCV suficiente (7+ velas diarias)
    2. Re-extraer features para todos los tokens
    3. Entrenar modelos RF + XGBoost (nueva version)
    4. Guardar modelos versionados + metadata

Usa el backend configurado en STORAGE_BACKEND (.env): sqlite o supabase.

Uso:
    python scripts/retrain_pipeline.py
    python scripts/retrain_pipeline.py --skip-labels    # Solo features + train
    python scripts/retrain_pipeline.py --skip-features   # Solo labels + train
    python scripts/retrain_pipeline.py --dry-run          # Solo mostrar stats
"""

import argparse
import sys
import time
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.data.supabase_storage import get_storage
from src.models.labeler import Labeler
from src.features.builder import FeatureBuilder
from src.models.trainer import ModelTrainer
from src.utils.logger import get_logger

logger = get_logger(__name__)


def run_pipeline(
    skip_labels: bool = False,
    skip_features: bool = False,
    dry_run: bool = False,
) -> dict:
    """
    Pipeline completo: label -> features -> train -> save.

    Args:
        skip_labels: Si True, no re-etiqueta (usa labels existentes).
        skip_features: Si True, no re-extrae features (usa los existentes).
        dry_run: Si True, solo muestra estadisticas sin entrenar.

    Returns:
        Dict con estadisticas del pipeline.
    """
    stats = {
        "tokens_total": 0,
        "labels_total": 0,
        "labels_positive": 0,
        "features_total": 0,
        "model_version": "",
        "rf_val_f1": 0.0,
        "xgb_val_f1": 0.0,
    }

    storage = get_storage()

    # ================================================================
    # PASO 1: Re-etiquetar tokens
    # ================================================================
    if not skip_labels:
        logger.info("=" * 60)
        logger.info("PASO 1: Re-etiquetando tokens con OHLCV suficiente")
        logger.info("=" * 60)

        t0 = time.time()
        labeler = Labeler(storage)
        labels_df = labeler.label_all_tokens()
        t1 = time.time()

        stats["labels_total"] = len(labels_df)
        if not labels_df.empty and "label_binary" in labels_df.columns:
            stats["labels_positive"] = int(labels_df["label_binary"].sum())

        logger.info(
            f"Etiquetados: {stats['labels_total']} tokens "
            f"({stats['labels_positive']} positivos) "
            f"en {t1 - t0:.1f}s"
        )
    else:
        logger.info("PASO 1: Saltando re-etiquetado (--skip-labels)")
        # Cargar labels existentes desde DB
        labels_df = storage.query("SELECT * FROM labels")
        stats["labels_total"] = len(labels_df)
        if not labels_df.empty and "label_binary" in labels_df.columns:
            stats["labels_positive"] = int(labels_df["label_binary"].sum())

    if labels_df.empty:
        logger.error("No hay labels. No se puede entrenar.")
        return stats

    # ================================================================
    # PASO 2: Re-extraer features
    # ================================================================
    if not skip_features:
        logger.info("=" * 60)
        logger.info("PASO 2: Extrayendo features para todos los tokens")
        logger.info("=" * 60)

        t0 = time.time()
        builder = FeatureBuilder(storage)
        features_df = builder.build_all_features()
        t1 = time.time()

        stats["features_total"] = len(features_df)
        logger.info(
            f"Features: {len(features_df)} tokens x {len(features_df.columns)} columnas "
            f"en {t1 - t0:.1f}s"
        )
    else:
        logger.info("PASO 2: Saltando extraccion de features (--skip-features)")
        # Cargar features existentes desde DB
        features_df = storage.query("SELECT * FROM features")
        stats["features_total"] = len(features_df)

    if features_df.empty:
        logger.error("No hay features. No se puede entrenar.")
        return stats

    # Estadisticas pre-entrenamiento
    db_stats = storage.stats()
    stats["tokens_total"] = db_stats.get("tokens", 0)

    logger.info("=" * 60)
    logger.info("RESUMEN PRE-ENTRENAMIENTO")
    logger.info(f"  Tokens en DB:     {stats['tokens_total']}")
    logger.info(f"  Labels:           {stats['labels_total']} ({stats['labels_positive']} positivos)")
    logger.info(f"  Features:         {stats['features_total']} tokens")
    logger.info(f"  OHLCV:            {db_stats.get('ohlcv', 0)} registros")
    logger.info("=" * 60)

    if dry_run:
        logger.info("[DRY RUN] No se entrena. Mostrando solo estadisticas.")
        return stats

    # ================================================================
    # PASO 3: Entrenar modelos
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 3: Entrenando modelos RF + XGBoost")
    logger.info("=" * 60)

    t0 = time.time()
    trainer = ModelTrainer(random_seed=42)
    results = trainer.train_all(features_df, labels_df, target="label_binary")
    t1 = time.time()

    logger.info(f"Entrenamiento completado en {t1 - t0:.1f}s")

    # Extraer metricas de validacion
    # Claves directas: cv_f1_mean, val_f1, val_accuracy (no anidadas)
    for model_name, model_results in results.items():
        if not isinstance(model_results, dict):
            continue

        f1 = model_results.get("val_f1", 0.0)
        cv_f1 = model_results.get("cv_f1_mean", 0.0)
        val_acc = model_results.get("val_accuracy", 0.0)

        logger.info(
            f"  {model_name}: CV_F1={cv_f1:.3f} Val_F1={f1:.3f} "
            f"Acc={val_acc:.3f}"
        )

        if "random_forest" in model_name.lower():
            stats["rf_val_f1"] = f1
        elif "xgboost" in model_name.lower():
            stats["xgb_val_f1"] = f1

    # ================================================================
    # PASO 4: Guardar modelos versionados
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 4: Guardando modelos versionados")
    logger.info("=" * 60)

    version_dir = trainer.save_models_versioned()
    stats["model_version"] = version_dir.name

    logger.info(f"Modelos guardados en: {version_dir}")

    # ================================================================
    # RESUMEN FINAL
    # ================================================================
    logger.info("=" * 60)
    logger.info("PIPELINE COMPLETADO")
    logger.info(f"  Version:          {stats['model_version']}")
    logger.info(f"  Tokens:           {stats['tokens_total']}")
    logger.info(f"  Labels:           {stats['labels_total']} ({stats['labels_positive']} pos)")
    logger.info(f"  Features:         {stats['features_total']}")
    logger.info(f"  RF Val F1:        {stats['rf_val_f1']:.3f}")
    logger.info(f"  XGB Val F1:       {stats['xgb_val_f1']:.3f}")
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Pipeline completo: label -> features -> train"
    )
    parser.add_argument(
        "--skip-labels", action="store_true",
        help="No re-etiquetar, usar labels existentes"
    )
    parser.add_argument(
        "--skip-features", action="store_true",
        help="No re-extraer features, usar los existentes"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo mostrar estadisticas, no entrenar"
    )

    args = parser.parse_args()

    stats = run_pipeline(
        skip_labels=args.skip_labels,
        skip_features=args.skip_features,
        dry_run=args.dry_run,
    )

    print(f"\nResultado: {stats}")
