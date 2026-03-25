#!/usr/bin/env python3
"""
check_drift.py - Verifica si los modelos ML necesitan re-entrenamiento.

Reemplaza a check_retrain_needed.sh con un script Python que usa
DriftDetector.generate_report() para hacer tres verificaciones ligeras:
  1. Time drift: dias desde el ultimo entrenamiento.
  2. Volume drift: labels nuevos acumulados desde el ultimo entrenamiento.
  3. Feature drift: cambio en medianas de features actuales vs entrenamiento.

Flujo:
  1. Carga metadata y train_medians desde disco local (DriftDetector.load_from_local).
  2. Calcula medianas actuales de features desde Supabase (ultimos 30 dias).
  3. Genera reporte completo con DriftDetector.generate_report().
  4. Guarda reporte en Supabase (tabla drift_reports).
  5. Imprime resumen a stdout.

Codigos de salida:
  0 — No se necesita re-entrenamiento (o modelos no disponibles, skip graceful).
  1 — Re-entrenamiento recomendado (GitHub Actions puede disparar retrain).
  2 — Error inesperado.

Uso:
    python scripts/check_drift.py
    python scripts/check_drift.py --model-version v12
    python scripts/check_drift.py --dry-run --verbose
"""

import argparse
import json
import os
import sys
from pathlib import Path

# Agregar el directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.utils.logger import get_logger

logger = get_logger(__name__)

# Codigos de salida
EXIT_OK = 0           # No necesita re-entrenamiento
EXIT_RETRAIN = 1      # Si necesita re-entrenamiento
EXIT_ERROR = 2        # Error inesperado


def calculate_current_medians(storage) -> dict:
    """
    Calcula medianas actuales de features desde Supabase (ultimos 30 dias).

    Consulta la tabla features, filtra por los ultimos 30 dias (si hay
    columna created_at), y calcula la mediana de cada feature numerica
    usando pandas.

    Args:
        storage: Instancia de SupabaseStorage con conexion activa.

    Returns:
        Dict con medianas por feature: {"feature_name": valor, ...}
        Dict vacio si no hay datos o hay error.
    """
    import pandas as pd

    logger.info("Calculando medianas actuales de features (ultimos 30 dias)...")

    try:
        # Intentar obtener features de los ultimos 30 dias
        # La tabla features tiene: token_id, data (JSONB), created_at
        df = storage.query("""
            SELECT data
            FROM features
            WHERE created_at >= NOW() - INTERVAL '30 days'
        """)

        # Si no hay datos recientes, usar todos los features
        if df.empty:
            logger.warning(
                "No hay features de los ultimos 30 dias. "
                "Usando todos los features disponibles."
            )
            df = storage.query("SELECT data FROM features")

        if df.empty:
            logger.warning("No hay features en la base de datos.")
            return {}

        # Desempaquetar JSONB a columnas planas
        features_expanded = pd.json_normalize(df["data"])

        if features_expanded.empty:
            return {}

        # Calcular mediana de cada columna numerica
        medians = {}
        for col in features_expanded.columns:
            try:
                # Convertir a numerico, ignorar errores
                numeric_col = pd.to_numeric(features_expanded[col], errors="coerce")
                median_val = numeric_col.median()
                if pd.notna(median_val):
                    medians[col] = float(median_val)
            except Exception:
                continue

        logger.info(
            f"Medianas calculadas: {len(medians)} features "
            f"(de {len(features_expanded)} tokens)"
        )
        return medians

    except Exception as e:
        logger.error(f"Error calculando medianas actuales: {e}")
        return {}


def write_github_output(key: str, value: str):
    """
    Escribe un output para GitHub Actions (si esta en CI).

    En GitHub Actions, los outputs se escriben al archivo indicado
    por la variable de entorno GITHUB_OUTPUT.

    Args:
        key: Nombre del output (ej: "needs_retrain").
        value: Valor del output (ej: "true").
    """
    github_output = os.environ.get("GITHUB_OUTPUT")
    if github_output:
        with open(github_output, "a") as fh:
            fh.write(f"{key}={value}\n")


def main(
    model_version: str = None,
    dry_run: bool = False,
    verbose: bool = False,
) -> int:
    """
    Ejecuta el pipeline completo de drift detection.

    Args:
        model_version: Version del modelo (ej: "v12"). Si None, auto-detecta.
        dry_run: Si True, no guarda reporte en Supabase ni exporta outputs.
        verbose: Si True, imprime detalles por feature.

    Returns:
        Codigo de salida: 0 (OK), 1 (retrain), 2 (error).
    """
    logger.info("=" * 60)
    logger.info("DRIFT DETECTION - Verificacion de re-entrenamiento")
    logger.info("=" * 60)

    if dry_run:
        logger.info("  Modo: DRY RUN (no guarda reporte)")
    if verbose:
        logger.info("  Modo: VERBOSE (detalles por feature)")

    # ================================================================
    # Paso 1: Descargar modelos si no existen localmente
    # ================================================================
    logger.info("\n[1/4] Verificando artefactos del modelo...")

    try:
        from scripts.download_models import download_all
    except ImportError:
        logger.warning("No se pudo importar download_models. Continuando sin descarga.")
        download_all = None

    # Intentar descargar si no hay modelos locales
    try:
        from config import MODELS_DIR
    except ImportError:
        MODELS_DIR = Path("data/models")

    # Verificar si existen los archivos necesarios
    if model_version:
        version_dir = MODELS_DIR / model_version
    else:
        version_file = MODELS_DIR / "latest_version.txt"
        if version_file.exists():
            model_version = version_file.read_text().strip()
            version_dir = MODELS_DIR / model_version
        else:
            version_dir = None

    # Si no hay version local, intentar descargar
    needs_download = (
        version_dir is None
        or not (version_dir / "metadata.json").exists()
        or not (version_dir / "train_medians.json").exists()
    )

    if needs_download and download_all:
        logger.info("Artefactos no encontrados localmente, descargando de Supabase Storage...")
        try:
            stats = download_all(version=model_version)
            if not stats.get("downloaded"):
                logger.warning(
                    "No se descargaron modelos de Supabase Storage. "
                    "Probablemente no se ha entrenado ningun modelo todavia. "
                    "Saltando drift check."
                )
                write_github_output("needs_retrain", "false")
                return EXIT_OK
            # Actualizar model_version si se descargo
            if not model_version:
                model_version = stats.get("version")
        except Exception as e:
            logger.warning(
                f"No se pudieron descargar modelos: {e}. "
                "Saltando drift check (modelos no disponibles)."
            )
            write_github_output("needs_retrain", "false")
            return EXIT_OK

    # ================================================================
    # Paso 2: Cargar artefactos locales (metadata + train_medians)
    # ================================================================
    logger.info(f"\n[2/4] Cargando artefactos del modelo {model_version or '(auto)'}...")

    try:
        from src.models.drift_detector import DriftDetector
        metadata, train_medians = DriftDetector.load_from_local(model_version)
    except FileNotFoundError as e:
        logger.warning(
            f"Artefactos no disponibles: {e}. "
            "Saltando drift check hasta que se entrene un modelo."
        )
        write_github_output("needs_retrain", "false")
        return EXIT_OK
    except Exception as e:
        logger.error(f"Error cargando artefactos: {e}")
        return EXIT_ERROR

    # Determinar model_version final (puede venir de load_from_local)
    if not model_version:
        model_version = metadata.get("model_version", "unknown")

    logger.info(f"  Version: {model_version}")
    logger.info(f"  Entrenado: {metadata.get('trained_at', 'desconocido')}")
    logger.info(f"  Train size: {metadata.get('train_size', 'desconocido')}")
    logger.info(f"  Features en train_medians: {len(train_medians)}")

    # ================================================================
    # Paso 3: Calcular medianas actuales desde Supabase
    # ================================================================
    logger.info("\n[3/4] Consultando features actuales de Supabase...")

    try:
        from src.data.supabase_storage import get_storage
        storage = get_storage()
    except Exception as e:
        logger.error(f"Error conectando a storage: {e}")
        return EXIT_ERROR

    current_medians = calculate_current_medians(storage)

    if not current_medians:
        logger.warning(
            "No se pudieron calcular medianas actuales. "
            "Saltando drift check (sin datos de features)."
        )
        write_github_output("needs_retrain", "false")
        return EXIT_OK

    logger.info(f"  Features actuales: {len(current_medians)}")

    # ================================================================
    # Paso 4: Generar reporte de drift
    # ================================================================
    logger.info("\n[4/4] Generando reporte de drift...")

    try:
        report = DriftDetector.generate_report(
            model_version=model_version,
            metadata=metadata,
            train_medians=train_medians,
            current_medians=current_medians,
        )
    except Exception as e:
        logger.error(f"Error generando reporte de drift: {e}")
        return EXIT_ERROR

    # ================================================================
    # Guardar reporte en Supabase (si no es dry-run)
    # ================================================================
    if not dry_run:
        try:
            storage.save_drift_report(report)
            logger.info("Reporte guardado en Supabase (tabla drift_reports)")
        except Exception as e:
            logger.warning(f"Error guardando reporte en Supabase: {e}")
            # No fatal: el reporte se imprime igual
    else:
        logger.info("DRY RUN: reporte NO guardado en Supabase")

    # ================================================================
    # Exportar outputs para GitHub Actions
    # ================================================================
    needs_retrain = report.get("needs_retraining", False)

    if not dry_run:
        write_github_output("needs_retrain", "true" if needs_retrain else "false")
        write_github_output("reasons", json.dumps(report.get("reasons", [])))
        write_github_output("overall_score", str(report.get("overall_score", 0)))
        write_github_output("model_version", model_version)

    # ================================================================
    # Imprimir resumen
    # ================================================================
    print()
    print("=" * 60)
    print("REPORTE DE DRIFT")
    print("=" * 60)
    print(f"  Modelo:          {model_version}")
    print(f"  Necesita retrain: {'SI' if needs_retrain else 'NO'}")
    print(f"  Overall score:   {report.get('overall_score', 0):.4f}")
    print(f"  Razones:         {report.get('reasons', [])}")
    print()

    # Time drift
    days = report.get("time_drift_days")
    time_triggered = report.get("time_drift_triggered", False)
    print(f"  Time drift:      {'SI' if time_triggered else 'NO'} "
          f"({days} dias desde entrenamiento)" if days is not None
          else f"  Time drift:      {'SI' if time_triggered else 'NO'} (fecha desconocida)")

    # Volume drift
    new_labels = report.get("volume_drift_new_labels", 0)
    vol_triggered = report.get("volume_drift_triggered", False)
    print(f"  Volume drift:    {'SI' if vol_triggered else 'NO'} "
          f"({new_labels} labels nuevos)")

    # Feature drift
    feat_count = report.get("feature_drift_count", 0)
    feat_total = report.get("feature_drift_total", 0)
    feat_triggered = report.get("feature_drift_triggered", False)
    print(f"  Feature drift:   {'SI' if feat_triggered else 'NO'} "
          f"({feat_count}/{feat_total} features con drift)")

    # Detalles por feature (modo verbose)
    if verbose and report.get("feature_drift_details"):
        print()
        print("  Top features con drift:")
        print(f"  {'Feature':<35} {'Train':>10} {'Actual':>10} {'Shift':>10}")
        print("  " + "-" * 67)
        for feat, detail in report["feature_drift_details"].items():
            train_val = detail.get("train", 0)
            current_val = detail.get("current", 0)
            shift = detail.get("shift_pct", 0)
            print(f"  {feat:<35} {train_val:>10.4f} {current_val:>10.4f} {shift:>9.1%}")

    print()
    print("=" * 60)

    if needs_retrain:
        print("RESULTADO: RE-ENTRENAMIENTO RECOMENDADO")
        logger.warning("Drift detectado. Codigo de salida: 1 (retrain)")
        return EXIT_RETRAIN
    else:
        print("RESULTADO: Modelo OK, no necesita re-entrenamiento")
        logger.info("No drift significativo. Codigo de salida: 0 (ok)")
        return EXIT_OK


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Verifica si los modelos ML necesitan re-entrenamiento (drift detection)"
    )
    parser.add_argument(
        "--model-version", type=str, default=None,
        help="Version del modelo (ej: v12). Si no se indica, auto-detecta desde latest_version.txt."
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="No guardar reporte en Supabase ni exportar outputs de GitHub Actions."
    )
    parser.add_argument(
        "--verbose", action="store_true",
        help="Imprimir detalles de drift por feature."
    )

    args = parser.parse_args()

    try:
        exit_code = main(
            model_version=args.model_version,
            dry_run=args.dry_run,
            verbose=args.verbose,
        )
    except Exception as e:
        logger.error(f"Error inesperado: {e}", exc_info=True)
        exit_code = EXIT_ERROR

    sys.exit(exit_code)
