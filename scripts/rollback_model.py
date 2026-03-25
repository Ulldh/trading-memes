#!/usr/bin/env python3
"""
rollback_model.py - Rollback de modelos ML a una version anterior.

Actualiza latest_version.txt en Supabase Storage y en disco local
para apuntar a una version especificada. No borra archivos de la
version actual; simplemente cambia el puntero de "latest".

Uso:
    python scripts/rollback_model.py --to-version v11
    python scripts/rollback_model.py --to-version v12 --dry-run
"""

import argparse
import sys
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)


def rollback(to_version: str, dry_run: bool = False) -> dict:
    """
    Realiza rollback de modelos a una version especifica.

    Actualiza latest_version.txt tanto en disco local como en
    Supabase Storage para apuntar a la version indicada.

    Args:
        to_version: Version destino del rollback (ej: "v11").
        dry_run: Si True, solo muestra que haria sin ejecutar.

    Returns:
        Dict con resultado: version, local_updated, remote_updated, error.
    """
    result = {
        "to_version": to_version,
        "local_updated": False,
        "remote_updated": False,
        "error": None,
    }

    # Validar formato de version
    if not to_version.startswith("v") or not to_version[1:].isdigit():
        msg = f"Formato de version invalido: '{to_version}'. Esperado: v1, v2, v11, etc."
        logger.error(msg)
        result["error"] = msg
        return result

    logger.info("=" * 60)
    logger.info(f"ROLLBACK DE MODELO A {to_version}")
    logger.info("=" * 60)

    # ================================================================
    # 1. Verificar que la version destino existe (local o remota)
    # ================================================================
    version_exists_local = False
    version_exists_remote = False

    # Verificar en disco local
    try:
        from config import MODELS_DIR
        local_version_dir = MODELS_DIR / to_version
        version_exists_local = local_version_dir.exists()
        if version_exists_local:
            logger.info(f"  Version {to_version} encontrada en disco local: {local_version_dir}")
        else:
            logger.info(f"  Version {to_version} NO encontrada en disco local")
    except ImportError:
        MODELS_DIR = Path("data/models")
        local_version_dir = MODELS_DIR / to_version
        version_exists_local = local_version_dir.exists()

    # Verificar en Supabase Storage
    storage_bucket = None
    try:
        from src.models.model_storage import _get_supabase_client, BUCKET
        client = _get_supabase_client()
        storage_bucket = client.storage.from_(BUCKET)
        # Intentar descargar metadata.json de la version destino
        data = storage_bucket.download(f"{to_version}/metadata.json")
        version_exists_remote = True
        logger.info(f"  Version {to_version} encontrada en Supabase Storage")
    except Exception as e:
        logger.info(f"  Version {to_version} NO verificada en Supabase Storage: {e}")

    if not version_exists_local and not version_exists_remote:
        msg = (
            f"Version {to_version} no encontrada ni en disco local ni en Supabase Storage. "
            f"Verifica que la version exista antes de hacer rollback."
        )
        logger.error(msg)
        result["error"] = msg
        return result

    if dry_run:
        logger.info(f"\n[DRY RUN] Se actualizaria latest_version.txt a '{to_version}'")
        logger.info("  No se realizan cambios.")
        return result

    # ================================================================
    # 2. Actualizar latest_version.txt local
    # ================================================================
    try:
        local_latest = MODELS_DIR / "latest_version.txt"
        current_version = local_latest.read_text().strip() if local_latest.exists() else "(ninguna)"
        local_latest.write_text(to_version)
        result["local_updated"] = True
        logger.info(f"  Local: latest_version.txt {current_version} -> {to_version}")
    except Exception as e:
        logger.warning(f"  Error actualizando latest_version.txt local: {e}")

    # ================================================================
    # 3. Actualizar latest_version.txt en Supabase Storage
    # ================================================================
    if storage_bucket is not None:
        try:
            try:
                storage_bucket.remove(["latest_version.txt"])
            except Exception:
                pass
            storage_bucket.upload("latest_version.txt", to_version.encode())
            result["remote_updated"] = True
            logger.info(f"  Remoto: latest_version.txt -> {to_version}")
        except Exception as e:
            logger.warning(f"  Error actualizando latest_version.txt remoto: {e}")
    else:
        logger.info("  Supabase Storage no disponible, solo se actualizo local")

    # ================================================================
    # RESUMEN
    # ================================================================
    logger.info("=" * 60)
    if result["local_updated"] or result["remote_updated"]:
        logger.info(f"ROLLBACK EXITOSO a {to_version}")
        logger.info(f"  Local actualizado:  {'SI' if result['local_updated'] else 'NO'}")
        logger.info(f"  Remoto actualizado: {'SI' if result['remote_updated'] else 'NO'}")
    else:
        logger.error("ROLLBACK FALLIDO: no se pudo actualizar ningun latest_version.txt")
        result["error"] = "No se pudo actualizar latest_version.txt"
    logger.info("=" * 60)

    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Rollback de modelos ML a una version anterior"
    )
    parser.add_argument(
        "--to-version", required=True,
        help="Version destino del rollback (ej: v11, v12)"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo mostrar que haria, sin ejecutar"
    )

    args = parser.parse_args()
    result = rollback(to_version=args.to_version, dry_run=args.dry_run)

    print(f"\nResultado: {result}")

    # Exit code: 0 si exito, 1 si error
    sys.exit(0 if result["error"] is None else 1)
