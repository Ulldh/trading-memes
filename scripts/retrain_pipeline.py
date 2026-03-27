#!/usr/bin/env python3
"""
retrain_pipeline.py - Pipeline completo de re-entrenamiento.

Ejecuta en secuencia:
    1. Re-etiquetar todos los tokens con OHLCV suficiente (7+ velas diarias)
    2. Re-extraer features para todos los tokens
    3. Entrenar modelos RF + XGBoost (nueva version)
    4. Guardar modelos versionados + metadata
    5. Subir artefactos a Supabase Storage
    6. Validar nuevo modelo vs anterior (auto-rollback si degrada >5%)

Usa el backend configurado en STORAGE_BACKEND (.env): sqlite o supabase.

Uso:
    python scripts/retrain_pipeline.py
    python scripts/retrain_pipeline.py --skip-labels    # Solo features + train
    python scripts/retrain_pipeline.py --skip-features   # Solo labels + train
    python scripts/retrain_pipeline.py --dry-run          # Solo mostrar stats
    python scripts/retrain_pipeline.py --tuned-params data/models/tuned_params.json
    python scripts/retrain_pipeline.py --use-v12-features  # Comparar justo vs v12
"""

import argparse
import json
import os
import ssl
import sys
import time
import urllib.request
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

# Umbral de degradacion permitida (5%)
DEGRADATION_THRESHOLD = 0.05


def _download_from_supabase_storage(remote_path: str) -> bytes | None:
    """
    Descarga un archivo del bucket ml-models en Supabase Storage via urllib.

    No requiere supabase-py — usa la REST API directamente.
    Util en GitHub Actions donde no hay disco local con modelos.

    Args:
        remote_path: Ruta dentro del bucket (ej: "latest_version.txt", "v12/metadata.json").

    Returns:
        Bytes del archivo o None si falla.
    """
    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not supa_url or not supa_key:
        return None

    try:
        url = f"{supa_url}/storage/v1/object/ml-models/{remote_path}"
        ctx = ssl.create_default_context()
        req = urllib.request.Request(
            url,
            headers={
                "apikey": supa_key,
                "Authorization": f"Bearer {supa_key}",
            },
        )
        with urllib.request.urlopen(req, context=ctx) as resp:
            return resp.read()
    except Exception as e:
        logger.debug(f"  No se pudo descargar {remote_path} via REST: {e}")
        return None


def _get_baseline_version() -> str | None:
    """
    Obtiene la version de produccion actual (baseline) ANTES de entrenar.

    Busca en orden:
      1. Disco local: data/models/latest_version.txt
      2. Supabase Storage: latest_version.txt (REST)

    Returns:
        Nombre de la version (ej: "v12") o None si no existe.
    """
    # 1. Disco local
    try:
        from config import MODELS_DIR
        local_file = MODELS_DIR / "latest_version.txt"
        if local_file.exists():
            version = local_file.read_text().strip()
            if version:
                logger.info(f"  Baseline de produccion (local): {version}")
                return version
    except Exception as e:
        logger.debug(f"  No se pudo leer latest_version.txt local: {e}")

    # 2. Supabase Storage via REST
    data = _download_from_supabase_storage("latest_version.txt")
    if data is not None:
        version = data.decode().strip()
        if version:
            logger.info(f"  Baseline de produccion (remoto): {version}")
            return version

    logger.info("  No se encontro version baseline. Primera ejecucion.")
    return None


def _load_v12_feature_names() -> list[str]:
    """
    Carga la lista de feature_names del modelo v12.

    Estrategia de busqueda (en orden):
      1. Disco local: data/models/v12/metadata.json
      2. Supabase Storage: v12/metadata.json (REST)

    Returns:
        Lista de nombres de features, o lista vacia si no se encontro.
    """
    # 1. Intentar desde disco local
    try:
        from config import MODELS_DIR
        local_metadata = MODELS_DIR / "v12" / "metadata.json"
        if local_metadata.exists():
            with open(local_metadata) as f:
                metadata = json.load(f)
            features = metadata.get("feature_names", [])
            if features:
                logger.info(f"  v12 feature list cargada desde disco local: {len(features)} features")
                return features
    except Exception as e:
        logger.debug(f"  No se pudo cargar v12 metadata local: {e}")

    # 2. Fallback: Supabase Storage via REST
    data = _download_from_supabase_storage("v12/metadata.json")
    if data is not None:
        try:
            metadata = json.loads(data.decode())
            features = metadata.get("feature_names", [])
            if features:
                logger.info(f"  v12 feature list cargada desde Supabase Storage: {len(features)} features")
                return features
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            logger.debug(f"  v12/metadata.json no es valido: {e}")

    return []


def run_pipeline(
    skip_labels: bool = False,
    skip_features: bool = False,
    dry_run: bool = False,
    tuned_params_file: str | None = None,
    use_v12_features: bool = False,
) -> dict:
    """
    Pipeline completo: label -> features -> train -> save.

    Args:
        skip_labels: Si True, no re-etiqueta (usa labels existentes).
        skip_features: Si True, no re-extrae features (usa los existentes).
        dry_run: Si True, solo muestra estadisticas sin entrenar.
        tuned_params_file: Ruta a JSON con hiperparametros optimizados (de tune_models.py).
        use_v12_features: Si True, filtra features al set de v12 para comparacion justa.

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
        "lgb_val_f1": 0.0,
        # Validacion post-entrenamiento (paso 6)
        "validation_passed": None,       # True/False/None (None = no se pudo validar)
        "rollback": False,               # True si se hizo rollback
        "rollback_to": "",               # Version a la que se hizo rollback
        "prev_rf_val_f1": None,          # F1 del modelo anterior
        "prev_xgb_val_f1": None,         # F1 del modelo anterior
    }

    storage = get_storage()

    # ================================================================
    # Guardar version baseline (produccion actual) ANTES de cualquier
    # cambio, para comparar en Paso 6 contra el mejor modelo real
    # y no contra una version intermedia fallida.
    # ================================================================
    baseline_version = _get_baseline_version()

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

        # Paso 1b: Labels por tiers (mega_gem, standard_gem, etc.)
        logger.info("-" * 40)
        logger.info("PASO 1b: Clasificando tokens por tiers")
        logger.info("-" * 40)

        t0 = time.time()
        tiered_df = labeler.label_all_tokens_tiered()
        t1 = time.time()

        tiered_count = len(tiered_df) if not tiered_df.empty else 0
        logger.info(f"Tiers asignados: {tiered_count} tokens en {t1 - t0:.1f}s")
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
        # Usar get_features_df() en lugar de query() crudo para que
        # SupabaseStorage desempaquete el JSONB 'data' a columnas planas
        features_df = storage.get_features_df()
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
    # PASO 2.5: Asegurar que latest_version.txt existe localmente
    # En GitHub Actions no hay directorio data/models/ local.
    # Descargar desde Supabase Storage para que el trainer sepa la
    # version actual y pueda calcular la siguiente (ej: v12 -> v13).
    # ================================================================
    from config import MODELS_DIR as _MODELS_DIR_VER
    local_version_file = _MODELS_DIR_VER / "latest_version.txt"
    if not local_version_file.exists():
        logger.info("latest_version.txt no existe localmente, descargando de Supabase Storage...")
        data = _download_from_supabase_storage("latest_version.txt")
        if data is not None:
            version_text = data.decode().strip()
            _MODELS_DIR_VER.mkdir(parents=True, exist_ok=True)
            local_version_file.write_text(version_text)
            logger.info(f"  Descargada version remota: {version_text}")
        else:
            logger.warning("  No se pudo descargar latest_version.txt. Se asumira v1.")

    # ================================================================
    # PASO 2.7: Filtrar features al set de v12 si se pidio
    # (antes de entrenar, para comparacion justa con v12)
    # ================================================================
    if use_v12_features:
        v12_features = _load_v12_feature_names()
        if v12_features:
            available = [c for c in v12_features if c in features_df.columns]
            extra_cols = [c for c in features_df.columns if c not in v12_features and c != "token_id"]
            # Mantener token_id + features de v12
            keep_cols = ["token_id"] + available if "token_id" in features_df.columns else available
            features_df = features_df[keep_cols]
            logger.info(
                f"  --use-v12-features: {len(available)}/{len(v12_features)} features de v12 disponibles, "
                f"{len(extra_cols)} features nuevos descartados"
            )
        else:
            logger.warning("  --use-v12-features: no se pudo cargar feature list de v12. Usando todas.")

    # ================================================================
    # PASO 3: Entrenar modelos
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 3: Entrenando modelos RF + XGBoost + LightGBM")
    logger.info("=" * 60)

    if tuned_params_file:
        logger.info(f"  Usando hiperparametros tuneados de: {tuned_params_file}")

    t0 = time.time()
    trainer = ModelTrainer(random_seed=42)
    results = trainer.train_all(
        features_df, labels_df, target="label_binary",
        tuned_params_file=tuned_params_file,
    )
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
        elif "lightgbm" in model_name.lower():
            stats["lgb_val_f1"] = f1

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
    # PASO 5: Subir artefactos a Supabase Storage
    # (Sube archivos del modelo PERO NO actualiza latest_version.txt aun.
    #  Eso se hace tras la validacion en Paso 6.)
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 5: Subiendo artefactos a Supabase Storage")
    logger.info("=" * 60)

    supabase_available = False
    try:
        from src.models.model_storage import (
            _get_supabase_client, BUCKET, VERSION_FILES,
        )

        client = _get_supabase_client()
        storage_bucket = client.storage.from_(BUCKET)
        supabase_available = True

        # 5a. Subir archivos del modelo versionado (sin actualizar latest_version.txt)
        from config import MODELS_DIR as _MODELS_DIR, PROCESSED_DIR as _PROCESSED_DIR
        version_name = stats["model_version"]
        model_dir = _MODELS_DIR / version_name
        files_uploaded = 0

        for filename in VERSION_FILES:
            filepath = model_dir / filename
            if not filepath.exists():
                logger.debug(f"  {filename} no existe, saltando")
                continue
            remote_path = f"{version_name}/{filename}"
            try:
                with open(filepath, "rb") as f:
                    data = f.read()
                try:
                    storage_bucket.remove([remote_path])
                except Exception:
                    pass
                storage_bucket.upload(remote_path, data)
                files_uploaded += 1
                logger.info(f"  {filename} -> {remote_path}")
            except Exception as e:
                logger.warning(f"  Error subiendo {filename}: {e}")

        logger.info(f"  Modelos subidos: {files_uploaded} archivos")

        # 5b. Subir artefactos extra del dashboard
        extra_files = [
            (_MODELS_DIR / "evaluation_results.json", "extras/evaluation_results.json"),
            (_MODELS_DIR / "feature_columns.json", "extras/feature_columns.json"),
        ]

        extras_uploaded = 0
        for local_path, remote_path in extra_files:
            if not local_path.exists():
                logger.debug(f"  {local_path.name} no existe, saltando")
                continue
            try:
                with open(local_path, "rb") as f:
                    data = f.read()
                try:
                    storage_bucket.remove([remote_path])
                except Exception:
                    pass
                storage_bucket.upload(remote_path, data)
                extras_uploaded += 1
                logger.info(f"  {local_path.name} -> {remote_path}")
            except Exception as e:
                logger.warning(f"  Error subiendo {local_path.name}: {e}")

        logger.info(f"  Artefactos extra subidos: {extras_uploaded}")

    except Exception as e:
        logger.warning(f"  No se pudieron subir artefactos a Storage: {e}")
        logger.warning("  (Los modelos locales se guardaron correctamente)")

    # ================================================================
    # PASO 6: Validar nuevo modelo vs anterior
    # Compara RF val_F1 y XGB val_F1 entre la version nueva y la anterior.
    # Si AMBAS metricas caen mas del 5% -> rollback automatico.
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 6: Validando nuevo modelo vs version anterior")
    logger.info("=" * 60)

    # Determinar version baseline (produccion actual guardada al inicio)
    new_version = stats["model_version"]  # ej: "v13"
    prev_version = baseline_version  # ej: "v12" (la mejor version en produccion)

    if prev_version is None or prev_version == new_version:
        logger.info("  Primera version o sin baseline, no hay modelo anterior para comparar.")
        stats["validation_passed"] = True

        # Actualizar latest_version.txt en Supabase (primera version)
        if supabase_available:
            _update_latest_version_remote(storage_bucket, new_version)
    else:
        logger.info(f"  Comparando contra baseline de produccion: {prev_version}")
        # Cargar metadata de la version baseline (produccion actual)
        prev_metadata = _load_previous_metadata(prev_version, supabase_available,
                                                 storage_bucket if supabase_available else None)

        if prev_metadata is None:
            logger.warning(
                f"  No se encontro metadata de {prev_version}. "
                "Asumiendo validacion OK (sin referencia para comparar)."
            )
            stats["validation_passed"] = True
            if supabase_available:
                _update_latest_version_remote(storage_bucket, new_version)
        else:
            # Extraer metricas del modelo anterior
            prev_results = prev_metadata.get("results", {})
            prev_rf_f1 = prev_results.get("random_forest", {}).get("val_f1", 0.0)
            prev_xgb_f1 = prev_results.get("xgboost", {}).get("val_f1", 0.0)

            stats["prev_rf_val_f1"] = prev_rf_f1
            stats["prev_xgb_val_f1"] = prev_xgb_f1

            # Calcular degradacion
            new_rf_f1 = stats["rf_val_f1"]
            new_xgb_f1 = stats["xgb_val_f1"]

            rf_drop = prev_rf_f1 - new_rf_f1
            xgb_drop = prev_xgb_f1 - new_xgb_f1

            logger.info(f"  {prev_version} -> {new_version}:")
            logger.info(f"    RF  Val F1: {prev_rf_f1:.3f} -> {new_rf_f1:.3f} (delta: {-rf_drop:+.3f})")
            logger.info(f"    XGB Val F1: {prev_xgb_f1:.3f} -> {new_xgb_f1:.3f} (delta: {-xgb_drop:+.3f})")

            # Ambas metricas deben caer mas del umbral para rollback
            rf_degraded = rf_drop > DEGRADATION_THRESHOLD
            xgb_degraded = xgb_drop > DEGRADATION_THRESHOLD

            if rf_degraded and xgb_degraded:
                # ROLLBACK: ambas metricas degradaron mas del 5%
                logger.warning(
                    f"  AMBAS metricas degradaron >5%: "
                    f"RF {rf_drop:+.3f}, XGB {xgb_drop:+.3f}"
                )
                logger.warning(
                    f"  Nuevo modelo {new_version} degradó métricas. "
                    f"Rollback a {prev_version}"
                )

                stats["validation_passed"] = False
                stats["rollback"] = True
                stats["rollback_to"] = prev_version

                # Rollback: actualizar latest_version.txt a la version anterior
                # Local
                from config import MODELS_DIR as _MODELS_DIR_RB
                local_latest = _MODELS_DIR_RB / "latest_version.txt"
                local_latest.write_text(prev_version)
                logger.info(f"  latest_version.txt local -> {prev_version}")

                # Remoto (Supabase Storage)
                if supabase_available:
                    _update_latest_version_remote(storage_bucket, prev_version)

                logger.warning(
                    f"  Artefactos de {new_version} se conservan en Storage "
                    f"para analisis, pero latest apunta a {prev_version}"
                )
            else:
                # Validacion OK: al menos una metrica mejora o se mantiene
                logger.info("  Validacion OK: metricas dentro del umbral aceptable")
                stats["validation_passed"] = True

                # Actualizar latest_version.txt en Supabase
                if supabase_available:
                    _update_latest_version_remote(storage_bucket, new_version)

    # ================================================================
    # RESUMEN FINAL
    # ================================================================
    logger.info("=" * 60)
    if stats["rollback"]:
        logger.warning("PIPELINE COMPLETADO CON ROLLBACK")
        logger.warning(f"  Version entrenada: {stats['model_version']}")
        logger.warning(f"  Rollback a:        {stats['rollback_to']}")
    else:
        logger.info("PIPELINE COMPLETADO")
        logger.info(f"  Version:          {stats['model_version']}")
    logger.info(f"  Tokens:           {stats['tokens_total']}")
    logger.info(f"  Labels:           {stats['labels_total']} ({stats['labels_positive']} pos)")
    logger.info(f"  Features:         {stats['features_total']}")
    logger.info(f"  RF Val F1:        {stats['rf_val_f1']:.3f}")
    logger.info(f"  XGB Val F1:       {stats['xgb_val_f1']:.3f}")
    if stats.get("lgb_val_f1", 0) > 0:
        logger.info(f"  LGB Val F1:       {stats['lgb_val_f1']:.3f}")
    if stats["prev_rf_val_f1"] is not None:
        logger.info(f"  RF Val F1 (prev): {stats['prev_rf_val_f1']:.3f}")
        logger.info(f"  XGB Val F1 (prev):{stats['prev_xgb_val_f1']:.3f}")
    logger.info(f"  Validacion:       {'PASS' if stats['validation_passed'] else 'FAIL (rollback)'}")
    logger.info("=" * 60)

    return stats


def _load_previous_metadata(
    prev_version: str,
    supabase_available: bool,
    storage_bucket,
) -> dict | None:
    """
    Carga el metadata.json de la version anterior.

    Estrategia de busqueda (en orden):
      1. Disco local: data/models/{prev_version}/metadata.json
      2. Supabase Storage via supabase-py (si el cliente esta disponible)
      3. Supabase Storage via REST/urllib (fallback sin supabase-py,
         necesario en GitHub Actions donde no hay disco local ni siempre
         se dispone de supabase-py)

    Args:
        prev_version: Nombre de la version anterior (ej: "v12").
        supabase_available: Si el cliente de Supabase esta disponible.
        storage_bucket: Bucket de Supabase Storage (o None).

    Returns:
        Dict con metadata o None si no se encontro.
    """
    # 1. Intentar desde disco local
    try:
        from config import MODELS_DIR as _MODELS_DIR_META
        local_metadata = _MODELS_DIR_META / prev_version / "metadata.json"
        if local_metadata.exists():
            with open(local_metadata) as f:
                metadata = json.load(f)
            logger.info(f"  Metadata de {prev_version} cargada desde disco local")
            return metadata
    except Exception as e:
        logger.debug(f"  No se pudo cargar metadata local de {prev_version}: {e}")

    # 2. Intentar desde Supabase Storage via supabase-py
    if supabase_available and storage_bucket is not None:
        try:
            data = storage_bucket.download(f"{prev_version}/metadata.json")
            metadata = json.loads(data.decode())
            logger.info(f"  Metadata de {prev_version} cargada desde Supabase Storage (supabase-py)")
            return metadata
        except Exception as e:
            logger.debug(f"  No se pudo descargar metadata de {prev_version} via supabase-py: {e}")

    # 3. Fallback: Supabase Storage via REST/urllib (sin dependencias extra)
    remote_path = f"{prev_version}/metadata.json"
    data = _download_from_supabase_storage(remote_path)
    if data is not None:
        try:
            metadata = json.loads(data.decode())
            logger.info(f"  Metadata de {prev_version} cargada desde Supabase Storage (REST)")
            return metadata
        except json.JSONDecodeError as e:
            logger.debug(f"  metadata.json de {prev_version} no es JSON valido: {e}")

    return None


def _update_latest_version_remote(storage_bucket, version: str):
    """
    Actualiza latest_version.txt en Supabase Storage.

    Args:
        storage_bucket: Bucket de Supabase Storage.
        version: Version a establecer como latest (ej: "v13").
    """
    try:
        try:
            storage_bucket.remove(["latest_version.txt"])
        except Exception:
            pass
        storage_bucket.upload("latest_version.txt", version.encode())
        logger.info(f"  latest_version.txt remoto -> {version}")
    except Exception as e:
        logger.warning(f"  Error actualizando latest_version.txt remoto: {e}")


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
    parser.add_argument(
        "--tuned-params", type=str, default=None,
        help="Archivo JSON con hiperparametros optimizados (de tune_models.py)"
    )
    parser.add_argument(
        "--use-v12-features", action="store_true",
        help="Filtrar features al set de v12 (de metadata.json) para comparacion justa"
    )

    args = parser.parse_args()

    stats = run_pipeline(
        skip_labels=args.skip_labels,
        skip_features=args.skip_features,
        dry_run=args.dry_run,
        tuned_params_file=args.tuned_params,
        use_v12_features=args.use_v12_features,
    )

    print(f"\nResultado: {stats}")
