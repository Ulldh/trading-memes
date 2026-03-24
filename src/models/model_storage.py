"""
model_storage.py - Subida/descarga de modelos ML a Supabase Storage.

Permite sincronizar modelos joblib entre el disco local (data/models/)
y el bucket 'ml-models' en Supabase Storage. Esto permite que
GitHub Actions descargue modelos entrenados, y que Streamlit Cloud
acceda a los modelos sin tener el repositorio completo.

Estructura en Supabase Storage:
    ml-models/
        v11/
            random_forest.joblib
            xgboost.joblib
            metadata.json
            train_medians.json
        latest_version.txt

Uso:
    from src.models.model_storage import upload_version, download_version

    # Subir modelos tras entrenar
    upload_version("v11")

    # Descargar modelos en otro entorno
    download_version("v11")
    download_version()  # descarga la ultima version
"""

import os
from pathlib import Path
from typing import Optional

from src.utils.logger import get_logger

try:
    from config import MODELS_DIR, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY
except ImportError:
    MODELS_DIR = Path("data/models")
    SUPABASE_URL = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

logger = get_logger(__name__)

BUCKET = "ml-models"

# Archivos a sincronizar por version
VERSION_FILES = [
    "random_forest.joblib",
    "xgboost.joblib",
    "metadata.json",
    "train_medians.json",
]


def _get_supabase_client():
    """Crea un cliente supabase-py autenticado con service_role."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_ROLE_KEY:
        raise ValueError(
            "SUPABASE_URL y SUPABASE_SERVICE_ROLE_KEY necesarios en .env"
        )
    from supabase import create_client
    return create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def upload_version(
    version: str,
    base_path: Optional[Path] = None,
) -> dict:
    """
    Sube una version de modelos del disco local a Supabase Storage.

    Args:
        version: Nombre de la version (ej: "v11").
        base_path: Directorio base de modelos (default: MODELS_DIR).

    Returns:
        Dict con: version, files_uploaded, errors.
    """
    base_dir = Path(base_path) if base_path else MODELS_DIR
    version_dir = base_dir / version

    if not version_dir.exists():
        raise FileNotFoundError(f"Version '{version}' no encontrada en {base_dir}")

    client = _get_supabase_client()
    storage = client.storage.from_(BUCKET)

    stats = {"version": version, "files_uploaded": [], "errors": []}

    logger.info(f"Subiendo modelos {version} a Supabase Storage...")

    for filename in VERSION_FILES:
        filepath = version_dir / filename
        if not filepath.exists():
            logger.debug(f"  {filename} no existe, saltando")
            continue

        remote_path = f"{version}/{filename}"
        try:
            with open(filepath, "rb") as f:
                # Eliminar si ya existe (upsert)
                try:
                    storage.remove([remote_path])
                except Exception:
                    pass  # No existe, ok

                storage.upload(remote_path, f.read())
                stats["files_uploaded"].append(filename)
                logger.info(f"  {filename} -> {remote_path}")

        except Exception as e:
            logger.warning(f"  Error subiendo {filename}: {e}")
            stats["errors"].append(f"{filename}: {e}")

    # Actualizar latest_version.txt
    try:
        remote_latest = "latest_version.txt"
        try:
            storage.remove([remote_latest])
        except Exception:
            pass
        storage.upload(remote_latest, version.encode())
        logger.info(f"  latest_version.txt -> {version}")
    except Exception as e:
        logger.warning(f"  Error actualizando latest_version.txt: {e}")

    logger.info(
        f"Upload completado: {len(stats['files_uploaded'])} archivos, "
        f"{len(stats['errors'])} errores"
    )
    return stats


def download_version(
    version: Optional[str] = None,
    base_path: Optional[Path] = None,
) -> Path:
    """
    Descarga una version de modelos de Supabase Storage al disco local.

    Args:
        version: Nombre de la version (ej: "v11"). Si None, descarga la ultima.
        base_path: Directorio destino (default: MODELS_DIR).

    Returns:
        Path al directorio de la version descargada.
    """
    base_dir = Path(base_path) if base_path else MODELS_DIR
    client = _get_supabase_client()
    storage = client.storage.from_(BUCKET)

    # Si no se especifica version, leer latest_version.txt
    if version is None:
        try:
            data = storage.download("latest_version.txt")
            version = data.decode().strip()
            logger.info(f"Ultima version en Storage: {version}")
        except Exception as e:
            raise FileNotFoundError(f"No se pudo leer latest_version.txt: {e}")

    version_dir = base_dir / version
    version_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"Descargando modelos {version} desde Supabase Storage...")

    downloaded = 0
    for filename in VERSION_FILES:
        remote_path = f"{version}/{filename}"
        local_path = version_dir / filename

        try:
            data = storage.download(remote_path)
            with open(local_path, "wb") as f:
                f.write(data)
            downloaded += 1
            logger.info(f"  {remote_path} -> {local_path}")
        except Exception as e:
            logger.debug(f"  {filename} no disponible en Storage: {e}")

    # Actualizar latest_version.txt local
    latest_file = base_dir / "latest_version.txt"
    latest_file.write_text(version)

    logger.info(f"Download completado: {downloaded} archivos en {version_dir}")
    return version_dir
