#!/usr/bin/env python3
"""
download_models.py - Descarga modelos y artefactos ML desde Supabase Storage.

Pensado para ejecutarse al iniciar el contenedor Docker en Render.
Descarga del bucket 'ml-models':
  1. La ultima version de modelos (v12/random_forest.joblib, etc.)
  2. Artefactos extra del dashboard (evaluation_results.json, etc.)
  3. Crea copias de los .joblib en MODELS_DIR raiz (el dashboard busca ahi)

Es idempotente: si los archivos ya existen, los sobreescribe.
Es tolerante a fallos: si un archivo no existe en Storage, log warning y continua.

Uso:
    python scripts/download_models.py
    python scripts/download_models.py --version v12
"""

import argparse
import shutil
import sys
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from config import MODELS_DIR, PROCESSED_DIR
from src.utils.logger import get_logger

logger = get_logger(__name__)

BUCKET = "ml-models"

# Artefactos extra: (ruta remota en bucket, ruta local destino)
EXTRA_ARTIFACTS = [
    ("extras/evaluation_results.json", MODELS_DIR / "evaluation_results.json"),
    ("extras/feature_columns.json", MODELS_DIR / "feature_columns.json"),
    ("extras/shap_values.csv", PROCESSED_DIR / "shap_values.csv"),
    ("extras/X_train.csv", PROCESSED_DIR / "X_train.csv"),
    ("extras/features.parquet", PROCESSED_DIR / "features.parquet"),
    ("extras/sensitivity_analysis.csv", PROCESSED_DIR / "sensitivity_analysis.csv"),
]

# Archivos de la version
VERSION_FILES = [
    "random_forest.joblib",
    "xgboost.joblib",
    "metadata.json",
    "train_medians.json",
]

# Archivos .joblib que se copian a la raiz de MODELS_DIR para el dashboard
ROOT_JOBLIB_FILES = [
    "random_forest.joblib",
    "xgboost.joblib",
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


def _download_file(storage, remote_path: str, local_path: Path) -> bool:
    """Descarga un archivo del bucket al disco local."""
    try:
        data = storage.download(remote_path)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        size_kb = len(data) / 1024
        logger.info(f"  OK: {remote_path} -> {local_path} ({size_kb:.1f} KB)")
        return True
    except Exception as e:
        logger.warning(f"  SKIP: {remote_path} no disponible: {e}")
        return False


def download_all(version: str = None) -> dict:
    """
    Descarga modelos + artefactos extra desde Supabase Storage.

    Args:
        version: Version especifica (ej: "v12"). Si None, lee latest_version.txt del bucket.

    Returns:
        Dict con estadisticas: downloaded, skipped, errors.
    """
    stats = {"downloaded": [], "skipped": [], "version": ""}

    client = _get_supabase_client()
    storage = client.storage.from_(BUCKET)

    # Determinar version
    if version is None:
        try:
            data = storage.download("latest_version.txt")
            version = data.decode().strip()
            logger.info(f"Ultima version en Storage: {version}")
        except Exception as e:
            logger.error(f"No se pudo leer latest_version.txt del bucket: {e}")
            logger.error("Especifica la version con --version")
            return stats

    stats["version"] = version
    version_dir = MODELS_DIR / version
    version_dir.mkdir(parents=True, exist_ok=True)

    logger.info("=" * 60)
    logger.info(f"DESCARGA DE ARTEFACTOS ML - {version}")
    logger.info("=" * 60)

    # ================================================================
    # 1. Descargar archivos de la version
    # ================================================================
    logger.info(f"\n[1/3] Descargando modelos {version}...")

    for filename in VERSION_FILES:
        remote_path = f"{version}/{filename}"
        local_path = version_dir / filename
        ok = _download_file(storage, remote_path, local_path)
        if ok:
            stats["downloaded"].append(remote_path)
        else:
            stats["skipped"].append(remote_path)

    # ================================================================
    # 2. Descargar artefactos extra
    # ================================================================
    logger.info("\n[2/3] Descargando artefactos extra del dashboard...")

    for remote_path, local_path in EXTRA_ARTIFACTS:
        ok = _download_file(storage, remote_path, local_path)
        if ok:
            stats["downloaded"].append(remote_path)
        else:
            stats["skipped"].append(remote_path)

    # ================================================================
    # 3. Crear copias de .joblib en raiz de MODELS_DIR
    # ================================================================
    logger.info("\n[3/3] Copiando .joblib a raiz de MODELS_DIR...")

    for filename in ROOT_JOBLIB_FILES:
        src = version_dir / filename
        dst = MODELS_DIR / filename

        if not src.exists():
            logger.warning(f"  SKIP: {src} no existe, no se puede copiar a raiz")
            continue

        try:
            # Si dst es un symlink que apunta a src, eliminar el symlink primero
            if dst.exists() or dst.is_symlink():
                if dst.is_symlink() or dst.resolve() == src.resolve():
                    dst.unlink()

            # En Docker no hay symlinks confiables, usar copia directa
            shutil.copy2(src, dst)
            logger.info(f"  OK: {src.name} -> {dst}")
        except Exception as e:
            logger.warning(f"  ERROR copiando {filename} a raiz: {e}")

    # Actualizar latest_version.txt local
    latest_local = MODELS_DIR / "latest_version.txt"
    latest_local.write_text(version)
    logger.info(f"\n  latest_version.txt local -> {version}")

    # ================================================================
    # Resumen
    # ================================================================
    logger.info("=" * 60)
    logger.info("RESUMEN")
    logger.info(f"  Version:    {version}")
    logger.info(f"  Descargados: {len(stats['downloaded'])}")
    logger.info(f"  Saltados:    {len(stats['skipped'])}")
    logger.info("=" * 60)

    return stats


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Descarga modelos y artefactos ML desde Supabase Storage"
    )
    parser.add_argument(
        "--version", type=str, default=None,
        help="Version de modelos (ej: v12). Si no se indica, descarga la ultima."
    )

    args = parser.parse_args()
    stats = download_all(version=args.version)

    if not stats["downloaded"]:
        logger.error("No se descargo ningun archivo!")
        sys.exit(1)

    print(f"\nResultado: {stats}")
