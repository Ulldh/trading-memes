#!/usr/bin/env python3
"""
tune_models.py - Optimizacion de hiperparametros con Optuna.

Carga datos de Supabase (o local), ejecuta Optuna para RF, XGB, y LightGBM,
y guarda los mejores hiperparametros en un archivo JSON.

Uso:
    python scripts/tune_models.py --n-trials 100
    python scripts/tune_models.py --n-trials 50 --model xgboost
    python scripts/tune_models.py --n-trials 100 --use-v12-features
"""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

import numpy as np
import pandas as pd

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Modelos disponibles para tuning
VALID_MODELS = ("rf", "xgboost", "lightgbm", "all")

# Estimacion de tiempo por trial (segundos) — orientativo
_ESTIMATED_SECS_PER_TRIAL = {
    "rf": 8,
    "xgboost": 5,
    "lightgbm": 4,
}


def _load_v12_feature_names() -> list[str]:
    """
    Carga la lista de features de v12 desde metadata.json.

    Busca primero en disco local y luego en Supabase Storage.

    Returns:
        Lista de nombres de features de v12.

    Raises:
        FileNotFoundError: Si no se encuentra metadata.json en ningun lugar.
    """
    # 1. Intentar disco local
    try:
        from config import MODELS_DIR
        local_path = MODELS_DIR / "v12" / "metadata.json"
        if local_path.exists():
            with open(local_path) as f:
                metadata = json.load(f)
            features = metadata.get("feature_names", [])
            logger.info(f"Features v12 cargados desde disco local: {len(features)}")
            return features
    except ImportError:
        pass

    # 2. Intentar Supabase Storage via REST
    import os
    import ssl
    import urllib.request

    supa_url = os.getenv("SUPABASE_URL", "")
    supa_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if supa_url and supa_key:
        try:
            url = f"{supa_url}/storage/v1/object/ml-models/v12/metadata.json"
            ctx = ssl.create_default_context()
            req = urllib.request.Request(
                url,
                headers={
                    "apikey": supa_key,
                    "Authorization": f"Bearer {supa_key}",
                },
            )
            with urllib.request.urlopen(req, context=ctx) as resp:
                data = json.loads(resp.read().decode())
            features = data.get("feature_names", [])
            logger.info(f"Features v12 cargados desde Supabase Storage: {len(features)}")
            return features
        except Exception as e:
            logger.warning(f"No se pudo descargar metadata v12 de Supabase: {e}")

    raise FileNotFoundError(
        "No se encontro data/models/v12/metadata.json ni en disco ni en Supabase Storage."
    )


def _load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Carga features y labels desde el storage configurado (Supabase o SQLite).

    Returns:
        Tupla de (features_df, labels_df).

    Raises:
        ValueError: Si no hay datos suficientes.
    """
    from src.data.supabase_storage import get_storage

    storage = get_storage()

    # Cargar features (desempaqueta JSONB si es Supabase)
    logger.info("Cargando features desde storage...")
    features_df = storage.get_features_df()
    if features_df.empty:
        raise ValueError("No hay features en la base de datos.")
    logger.info(f"  Features: {len(features_df)} tokens x {len(features_df.columns)} columnas")

    # Cargar labels
    logger.info("Cargando labels desde storage...")
    labels_df = storage.query("SELECT * FROM labels")
    if labels_df.empty:
        raise ValueError("No hay labels en la base de datos.")
    logger.info(f"  Labels: {len(labels_df)} tokens")

    return features_df, labels_df


def _prepare_data(
    features_df: pd.DataFrame,
    labels_df: pd.DataFrame,
    v12_features: list[str] | None = None,
    seed: int = 42,
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series, list[str]]:
    """
    Prepara datos para tuning: merge, limpieza, filtrado de features, split.

    Replica la logica de ModelTrainer.prepare_data() para mantener coherencia
    con el pipeline de entrenamiento, pero permite filtrar a un subset de features.

    Args:
        features_df: DataFrame con features.
        labels_df: DataFrame con labels.
        v12_features: Si se proporciona, solo usa estas features (filtro v12).
        seed: Semilla para el split.

    Returns:
        Tupla de (X_train, y_train, X_val, y_val, feature_names).
    """
    from sklearn.model_selection import train_test_split

    target = "label_binary"

    # Asegurar que token_id sea columna
    if "token_id" not in features_df.columns and features_df.index.name == "token_id":
        features_df = features_df.reset_index()
    if "token_id" not in labels_df.columns and labels_df.index.name == "token_id":
        labels_df = labels_df.reset_index()

    # Merge inner: solo tokens con features Y labels
    merged_df = features_df.merge(labels_df, on="token_id", how="inner")
    logger.info(f"Despues de merge: {len(merged_df)} tokens con features y labels")

    if merged_df.empty:
        raise ValueError("No hay tokens en comun entre features y labels.")

    # Eliminar filas donde el target es NaN
    merged_df = merged_df.dropna(subset=[target])

    if merged_df.empty:
        raise ValueError("No quedan datos despues de eliminar NaN en el target.")

    # Separar features (X) y target (y)
    non_feature_cols = [
        "token_id", "label_multi", "label_binary",
        "max_multiple", "final_multiple", "return_7d", "notes",
        "labeled_at", "computed_at",
        # Columnas de tier (data leakage si se usan como features)
        "tier", "tier_numeric", "close_max_multiple",
        "chain", "symbol", "name", "dex_id", "pool_address",
        "first_seen", "last_updated",
    ]
    # Manejar sufijos _x/_y del merge
    suffixed_label_cols = [
        f"{col}_y" for col in non_feature_cols if f"{col}_y" in merged_df.columns
    ]
    non_feature_cols.extend(suffixed_label_cols)

    # Renombrar features con sufijo _x a su nombre original
    rename_map = {}
    for col in merged_df.columns:
        if col.endswith("_x"):
            base = col[:-2]
            if base not in merged_df.columns and f"{base}_y" in merged_df.columns:
                rename_map[col] = base
    if rename_map:
        merged_df = merged_df.rename(columns=rename_map)

    feature_cols = [
        col for col in merged_df.columns
        if col not in non_feature_cols
    ]

    # Solo columnas numericas
    feature_cols = [
        col for col in feature_cols
        if pd.api.types.is_numeric_dtype(merged_df[col])
    ]

    # Filtrar features excluidos por configuracion
    try:
        from config import EXCLUDED_FEATURES
        feature_cols = [c for c in feature_cols if c not in EXCLUDED_FEATURES]
    except ImportError:
        pass

    # Si se pide filtrar a v12 features, aplicar filtro
    if v12_features:
        available = set(feature_cols)
        v12_available = [f for f in v12_features if f in available]
        missing = [f for f in v12_features if f not in available]
        if missing:
            logger.warning(
                f"  {len(missing)} features de v12 no disponibles en los datos: "
                f"{missing[:5]}{'...' if len(missing) > 5 else ''}"
            )
        feature_cols = v12_available
        logger.info(f"Filtrado a features v12: {len(feature_cols)} de {len(v12_features)}")

    if not feature_cols:
        raise ValueError("No se encontraron columnas de features.")

    X = merged_df[feature_cols].copy()
    y = merged_df[target].copy()

    # Split train/val con estratificacion
    try:
        from config import ML_CONFIG
        test_size = ML_CONFIG.get("test_size", 0.2)
    except ImportError:
        test_size = 0.2

    min_class_count = y.value_counts().min()
    stratify = y if min_class_count >= 2 else None

    X_train, X_val, y_train, y_val = train_test_split(
        X, y,
        test_size=test_size,
        random_state=seed,
        stratify=stratify,
    )

    # Reemplazar infinitos y rellenar NaN con mediana de train
    X_train = X_train.replace([np.inf, -np.inf], np.nan)
    X_val = X_val.replace([np.inf, -np.inf], np.nan)
    train_medians = X_train.median()
    X_train = X_train.fillna(train_medians).fillna(0)
    X_val = X_val.fillna(train_medians).fillna(0)

    logger.info(
        f"Split: train={len(X_train)} ({(1 - test_size) * 100:.0f}%), "
        f"val={len(X_val)} ({test_size * 100:.0f}%)"
    )
    logger.info(f"Distribucion train:\n{y_train.value_counts().to_string()}")
    logger.info(f"Distribucion val:\n{y_val.value_counts().to_string()}")

    return X_train, y_train, X_val, y_val, feature_cols


def _estimate_time(model: str, n_trials: int) -> str:
    """
    Estima el tiempo total de tuning basado en el modelo y numero de trials.

    Args:
        model: Nombre del modelo ('rf', 'xgboost', 'lightgbm', 'all').
        n_trials: Numero de trials por modelo.

    Returns:
        String legible con la estimacion de tiempo.
    """
    if model == "all":
        total_secs = sum(
            _ESTIMATED_SECS_PER_TRIAL[m] * n_trials
            for m in ("rf", "xgboost", "lightgbm")
        )
    else:
        total_secs = _ESTIMATED_SECS_PER_TRIAL.get(model, 6) * n_trials

    if total_secs < 60:
        return f"~{total_secs}s"
    elif total_secs < 3600:
        return f"~{total_secs // 60}m {total_secs % 60}s"
    else:
        hours = total_secs // 3600
        mins = (total_secs % 3600) // 60
        return f"~{hours}h {mins}m"


def run_tuning(
    n_trials: int = 100,
    model: str = "all",
    use_v12_features: bool = False,
    seed: int = 42,
) -> dict:
    """
    Ejecuta el pipeline completo de tuning con Optuna.

    Pasos:
      1. Cargar datos de Supabase/SQLite.
      2. Filtrar features si se pide v12.
      3. Preparar datos (merge, split).
      4. Ejecutar tuning con HyperparamTuner.
      5. Guardar resultados en JSON.
      6. Imprimir resumen.

    Args:
        n_trials: Numero de trials de Optuna por modelo.
        model: Modelo a optimizar ('rf', 'xgboost', 'lightgbm', 'all').
        use_v12_features: Si True, solo usa features del set v12.
        seed: Semilla para reproducibilidad.

    Returns:
        Dict con resultados del tuning.
    """
    from src.models.tuner import HyperparamTuner

    # ================================================================
    # Paso 1: Cargar datos
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 1: Cargando datos desde storage")
    logger.info("=" * 60)

    features_df, labels_df = _load_data()

    # ================================================================
    # Paso 2: Filtrar features (opcional)
    # ================================================================
    v12_features = None
    if use_v12_features:
        logger.info("=" * 60)
        logger.info("PASO 2: Cargando lista de features v12")
        logger.info("=" * 60)
        v12_features = _load_v12_feature_names()
        logger.info(f"  Features v12: {len(v12_features)} nombres cargados")
    else:
        logger.info("PASO 2: Usando TODOS los features disponibles (sin filtro v12)")

    # ================================================================
    # Paso 3: Preparar datos
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 3: Preparando datos (merge, split)")
    logger.info("=" * 60)

    X_train, y_train, X_val, y_val, feature_names = _prepare_data(
        features_df, labels_df,
        v12_features=v12_features,
        seed=seed,
    )

    logger.info(f"  Features finales: {len(feature_names)}")
    logger.info(f"  Train: {len(X_train)} muestras, Val: {len(X_val)} muestras")

    # ================================================================
    # Paso 4: Estimar tiempo y ejecutar tuning
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 4: Ejecutando optimizacion con Optuna")
    logger.info("=" * 60)

    est_time = _estimate_time(model, n_trials)
    logger.info(f"  Modelo(s): {model}")
    logger.info(f"  Trials por modelo: {n_trials}")
    logger.info(f"  Tiempo estimado: {est_time}")
    logger.info("")

    tuner = HyperparamTuner(
        X_train, y_train, X_val, y_val,
        n_trials=n_trials,
        random_seed=seed,
    )

    t0 = time.time()

    if model == "all":
        tuner.tune_all()
    elif model == "rf":
        tuner.tune_random_forest()
    elif model == "xgboost":
        tuner.tune_xgboost()
    elif model == "lightgbm":
        tuner.tune_lightgbm()

    elapsed = time.time() - t0

    # ================================================================
    # Paso 5: Guardar resultados en JSON
    # ================================================================
    logger.info("=" * 60)
    logger.info("PASO 5: Guardando resultados")
    logger.info("=" * 60)

    try:
        from config import MODELS_DIR
    except ImportError:
        MODELS_DIR = Path("data/models")

    output_path = MODELS_DIR / "tuning_results.json"

    # Construir resultado enriquecido con metadata de reproducibilidad
    output = {}
    for model_name, params in tuner.best_params.items():
        study = tuner.studies.get(model_name)
        output[model_name] = {
            "best_params": _serialize_params(params),
            "best_f1_cv": float(study.best_value) if study else None,
            "n_trials": n_trials,
            "cv_folds": tuner.cv_folds,
            "random_seed": seed,
        }

    # Metadata de reproducibilidad
    output["_metadata"] = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "n_trials": n_trials,
        "seed": seed,
        "use_v12_features": use_v12_features,
        "feature_count": len(feature_names),
        "feature_names": feature_names,
        "train_samples": len(X_train),
        "val_samples": len(X_val),
        "positive_train": int(y_train.sum()),
        "positive_val": int(y_val.sum()),
        "elapsed_seconds": round(elapsed, 1),
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    logger.info(f"Resultados guardados en: {output_path}")

    # ================================================================
    # Paso 6: Resumen
    # ================================================================
    logger.info("")
    logger.info("=" * 60)
    logger.info("RESUMEN DE TUNING")
    logger.info("=" * 60)
    logger.info(f"  Tiempo total:     {elapsed:.1f}s")
    logger.info(f"  Features usados:  {len(feature_names)}")
    logger.info(f"  Train/Val:        {len(X_train)}/{len(X_val)}")
    logger.info("")

    for model_name, study in tuner.studies.items():
        logger.info(f"  {model_name}:")
        logger.info(f"    Mejor F1 (CV): {study.best_value:.4f}")
        best_p = tuner.best_params[model_name]
        # Mostrar los 5 parametros mas relevantes
        for key, value in list(best_p.items())[:5]:
            logger.info(f"    {key}: {value}")
        if len(best_p) > 5:
            logger.info(f"    ... y {len(best_p) - 5} parametros mas")
        logger.info("")

    logger.info("=" * 60)
    logger.info("SIGUIENTE PASO:")
    logger.info(
        "  Para re-entrenar con los mejores hiperparametros:"
    )
    logger.info(
        f"  python scripts/retrain_pipeline.py "
        f"--tuned-params {output_path}"
    )
    logger.info("=" * 60)

    return output


def _serialize_params(params: dict) -> dict:
    """
    Convierte parametros a tipos JSON-serializables.

    numpy int64/float64 no son serializables por defecto en json.dump.

    Args:
        params: Diccionario de hiperparametros.

    Returns:
        Diccionario con tipos nativos de Python.
    """
    serialized = {}
    for key, value in params.items():
        if isinstance(value, (np.integer,)):
            serialized[key] = int(value)
        elif isinstance(value, (np.floating,)):
            serialized[key] = float(value)
        elif isinstance(value, np.bool_):
            serialized[key] = bool(value)
        else:
            serialized[key] = value
    return serialized


def main():
    """Punto de entrada del script con argumentos de linea de comandos."""
    parser = argparse.ArgumentParser(
        description="Optimizacion de hiperparametros con Optuna para RF, XGB, LightGBM."
    )
    parser.add_argument(
        "--n-trials", type=int, default=100,
        help="Numero de trials de Optuna por modelo (default: 100)"
    )
    parser.add_argument(
        "--model", type=str, default="all",
        choices=VALID_MODELS,
        help="Modelo a optimizar: rf, xgboost, lightgbm, all (default: all)"
    )
    parser.add_argument(
        "--use-v12-features", action="store_true",
        help="Solo usar el set de features de v12 (excluir features nuevos)"
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Semilla para reproducibilidad (default: 42)"
    )

    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("tune_models.py - Optimizacion de hiperparametros con Optuna")
    logger.info("=" * 60)
    logger.info(f"  Trials:          {args.n_trials}")
    logger.info(f"  Modelo(s):       {args.model}")
    logger.info(f"  Features v12:    {'Si' if args.use_v12_features else 'No (todos)'}")
    logger.info(f"  Seed:            {args.seed}")
    logger.info("")

    try:
        results = run_tuning(
            n_trials=args.n_trials,
            model=args.model,
            use_v12_features=args.use_v12_features,
            seed=args.seed,
        )
        print(f"\nResultado: {json.dumps({k: v for k, v in results.items() if k != '_metadata'}, indent=2)}")
        return 0

    except ImportError as e:
        logger.error(f"Dependencia faltante: {e}")
        logger.error("Instalar con: pip install optuna>=3.0 lightgbm>=4.0")
        return 1

    except ValueError as e:
        logger.error(f"Error de datos: {e}")
        return 1

    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
