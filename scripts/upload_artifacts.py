#!/usr/bin/env python3
"""
upload_artifacts.py - Sube TODOS los artefactos ML a Supabase Storage.

Sube al bucket 'ml-models':
  1. Modelos versionados (v12/random_forest.joblib, xgboost.joblib, metadata.json, train_medians.json)
  2. Artefactos extra del dashboard:
     - evaluation_results.json
     - feature_columns.json
     - processed/shap_values.csv
     - processed/X_train.csv
     - processed/features.parquet
     - processed/sensitivity_analysis.csv

La estructura en el bucket queda:
    ml-models/
        v12/
            random_forest.joblib
            xgboost.joblib
            metadata.json
            train_medians.json
        extras/
            evaluation_results.json
            feature_columns.json
            shap_values.csv
            X_train.csv
            features.parquet
            sensitivity_analysis.csv
        latest_version.txt

Uso:
    python scripts/upload_artifacts.py
    python scripts/upload_artifacts.py --version v12
    python scripts/upload_artifacts.py --dry-run
"""

import argparse
import sys
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from config import MODELS_DIR, PROCESSED_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

BUCKET = "ml-models"

# Artefactos extra que necesita el dashboard (fuera de la carpeta de version)
EXTRA_ARTIFACTS = [
    # (ruta_local_relativa_a_DATA_DIR, ruta_remota_en_bucket)
    (MODELS_DIR / "evaluation_results.json", "extras/evaluation_results.json"),
    (MODELS_DIR / "feature_columns.json", "extras/feature_columns.json"),
    (PROCESSED_DIR / "shap_values.csv", "extras/shap_values.csv"),
    (PROCESSED_DIR / "X_train.csv", "extras/X_train.csv"),
    (PROCESSED_DIR / "features.parquet", "extras/features.parquet"),
    (PROCESSED_DIR / "sensitivity_analysis.csv", "extras/sensitivity_analysis.csv"),
]


def _get_supabase_client():
    """Crea un cliente supabase-py con service_role key."""
    import os
    from dotenv import load_dotenv
    load_dotenv()

    url = os.getenv("SUPABASE_URL", "")
    key = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

    if not url or not key:
        raise ValueError(
            "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY necesarios en .env"
        )

    from supabase import create_client
    return create_client(url, key)


def _upload_file(storage, local_path: Path, remote_path: str) -> bool:
    """Sube un archivo al bucket, sobreescribiendo si ya existe."""
    try:
        with open(local_path, "rb") as f:
            data = f.read()

        # Intentar eliminar si ya existe (upsert)
        try:
            storage.remove([remote_path])
        except Exception:
            pass

        storage.upload(remote_path, data)
        size_kb = len(data) / 1024
        logger.info(f"  OK: {local_path.name} -> {remote_path} ({size_kb:.1f} KB)")
        return True

    except Exception as e:
        logger.warning(f"  ERROR: {local_path.name} -> {remote_path}: {e}")
        return False


def upload_all(version: str = None, dry_run: bool = False) -> dict:
    """
    Sube modelos versionados + artefactos extra al bucket ml-models.

    Args:
        version: Version de modelos a subir (ej: "v12"). Si None, lee latest_version.txt.
        dry_run: Si True, solo muestra que se subiria sin subir.

    Returns:
        Dict con estadisticas: uploaded, skipped, errors.
    """
    stats = {"uploaded": [], "skipped": [], "errors": []}

    # Determinar version
    if version is None:
        latest_file = MODELS_DIR / "latest_version.txt"
        if latest_file.exists():
            version = latest_file.read_text().strip()
            logger.info(f"Version detectada de latest_version.txt: {version}")
        else:
            raise FileNotFoundError(
                "No se especifico version y no existe latest_version.txt"
            )

    version_dir = MODELS_DIR / version
    if not version_dir.exists():
        raise FileNotFoundError(f"Directorio {version_dir} no existe")

    logger.info("=" * 60)
    logger.info(f"SUBIDA DE ARTEFACTOS ML - {version}")
    logger.info("=" * 60)

    # Recolectar todos los archivos a subir
    files_to_upload = []

    # 1. Archivos de la version (modelos + metadata)
    version_files = [
        "random_forest.joblib",
        "xgboost.joblib",
        "metadata.json",
        "train_medians.json",
    ]
    for filename in version_files:
        local_path = version_dir / filename
        remote_path = f"{version}/{filename}"
        if local_path.exists():
            files_to_upload.append((local_path, remote_path))
        else:
            logger.debug(f"  {filename} no existe en {version_dir}, saltando")
            stats["skipped"].append(filename)

    # 2. Artefactos extra
    for local_path, remote_path in EXTRA_ARTIFACTS:
        if local_path.exists():
            files_to_upload.append((local_path, remote_path))
        else:
            logger.warning(f"  {local_path.name} no existe, saltando")
            stats["skipped"].append(str(local_path.name))

    # Mostrar plan
    logger.info(f"\nArchivos a subir: {len(files_to_upload)}")
    for local_path, remote_path in files_to_upload:
        size_kb = local_path.stat().st_size / 1024
        logger.info(f"  {local_path.name} ({size_kb:.1f} KB) -> {remote_path}")

    if dry_run:
        logger.info("\n[DRY RUN] No se sube nada.")
        return stats

    # Subir archivos
    logger.info(f"\nSubiendo a bucket '{BUCKET}'...")
    client = _get_supabase_client()
    storage = client.storage.from_(BUCKET)

    for local_path, remote_path in files_to_upload:
        ok = _upload_file(storage, local_path, remote_path)
        if ok:
            stats["uploaded"].append(remote_path)
        else:
            stats["errors"].append(remote_path)

    # Actualizar latest_version.txt en el bucket
    try:
        try:
            storage.remove(["latest_version.txt"])
        except Exception:
            pass
        storage.upload("latest_version.txt", version.encode())
        logger.info(f"  OK: latest_version.txt -> {version}")
    except Exception as e:
        logger.warning(f"  ERROR actualizando latest_version.txt: {e}")

    # Resumen
    logger.info("=" * 60)
    logger.info("RESUMEN")
    logger.info(f"  Subidos:  {len(stats['uploaded'])}")
    logger.info(f"  Saltados: {len(stats['skipped'])}")
    logger.info(f"  Errores:  {len(stats['errors'])}")
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Sube artefactos ML a Supabase Storage"
    )
    parser.add_argument(
        "--version", type=str, default=None,
        help="Version de modelos (ej: v12). Si no se indica, lee latest_version.txt."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo mostrar que se subiria, sin subir."
    )

    args = parser.parse_args()
    stats = upload_all(version=args.version, dry_run=args.dry_run)
    print(f"\nResultado: {stats}")
