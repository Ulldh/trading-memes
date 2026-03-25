"""
drift_detector.py - Detecta cuando los modelos ML necesitan re-entrenamiento.

Este modulo implementa tecnicas de deteccion de "drift" (cambio en la distribucion
de datos) que pueden degradar el rendimiento de modelos ML con el tiempo.

Tipos de drift detectados:
1. **Data Drift**: Cambio en la distribucion de features (X).
   - Metodo: Kolmogorov-Smirnov (KS) test para cada feature.
   - Umbral: p-value < 0.05 indica drift significativo.

2. **Concept Drift**: Cambio en la relacion entre features y target (X -> y).
   - Metodo: F1 score en nuevos datos cae por debajo de umbral.
   - Umbral: F1 < 0.5 indica modelo desactualizado.

3. **Volume Drift**: Aumento significativo en el volumen de datos.
   - Metodo: Numero de tokens nuevos etiquetados.
   - Umbral: +50 tokens nuevos desde ultimo entrenamiento.

Conceptos clave:
    - Drift: Cambio en la distribucion de datos que degrada el modelo.
    - KS Test: Test estadistico que compara dos distribuciones.
    - p-value: Probabilidad de que las distribuciones sean iguales.
      - p-value < 0.05: Distribuciones significativamente diferentes (drift).
      - p-value >= 0.05: Distribuciones similares (no drift).

Uso:
    from src.models.drift_detector import DriftDetector

    detector = DriftDetector()

    # Verificar drift
    drift_report = detector.detect_all_drift(
        train_data=X_train,
        new_data=X_new,
        model=trained_model,
        y_new=y_new
    )

    if drift_report["needs_retraining"]:
        print("¡Modelo necesita re-entrenamiento!")
        print(f"Razones: {drift_report['reasons']}")
"""

import json
import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timezone, timedelta

from scipy.stats import ks_2samp
from sklearn.metrics import f1_score, accuracy_score

from src.utils.logger import get_logger

logger = get_logger(__name__)


class DriftDetector:
    """
    Detecta cuando un modelo de ML necesita re-entrenamiento debido a drift.

    Implementa tres tipos de deteccion:
    1. Data drift (cambio en distribucion de features).
    2. Concept drift (degradacion de F1 score).
    3. Volume drift (acumulacion de nuevos datos).

    Args:
        ks_threshold: Umbral de p-value para KS test (default: 0.05).
        f1_threshold: Umbral minimo de F1 score (default: 0.5).
        volume_threshold: Numero minimo de tokens nuevos (default: 50).
        days_threshold: Dias maximos sin re-entrenar (default: 30).

    Ejemplo:
        >>> detector = DriftDetector()
        >>> report = detector.detect_all_drift(X_train, X_new, model, y_new)
        >>> if report["needs_retraining"]:
        ...     print(f"Razones: {report['reasons']}")
    """

    def __init__(
        self,
        ks_threshold: float = 0.05,
        f1_threshold: float = 0.5,
        volume_threshold: int = 50,
        days_threshold: int = 30,
    ):
        """
        Inicializa el detector con umbrales configurables.

        Args:
            ks_threshold: p-value maximo para KS test (0.05 = 5% significancia).
            f1_threshold: F1 score minimo aceptable (0.5 = 50%).
            volume_threshold: Tokens nuevos minimos para re-entrenar (50).
            days_threshold: Dias maximos sin re-entrenar (30).
        """
        self.ks_threshold = ks_threshold
        self.f1_threshold = f1_threshold
        self.volume_threshold = volume_threshold
        self.days_threshold = days_threshold

        logger.info(
            f"DriftDetector inicializado: KS={ks_threshold}, "
            f"F1={f1_threshold}, Vol={volume_threshold}, Days={days_threshold}"
        )

    # ============================================================
    # 1. DATA DRIFT (cambio en distribucion de features)
    # ============================================================

    def detect_data_drift(
        self,
        train_data: pd.DataFrame,
        new_data: pd.DataFrame,
    ) -> Dict[str, any]:
        """
        Detecta data drift usando Kolmogorov-Smirnov test.

        Para cada feature:
        1. Aplica KS test entre distribucion de entrenamiento y nuevos datos.
        2. Si p-value < threshold, hay drift significativo en esa feature.

        Args:
            train_data: DataFrame con features de entrenamiento.
            new_data: DataFrame con features nuevos (mismas columnas).

        Returns:
            Dict con:
            - has_drift (bool): True si al menos 1 feature tiene drift.
            - drifted_features (list): Features con drift significativo.
            - drift_details (dict): {feature: (statistic, p_value)}.

        Ejemplo:
            >>> result = detector.detect_data_drift(X_train, X_new)
            >>> if result["has_drift"]:
            ...     print(f"Features con drift: {result['drifted_features']}")
        """
        logger.info(
            f"Detectando data drift: {len(train_data)} train vs {len(new_data)} new"
        )

        # Verificar que tienen las mismas columnas
        if list(train_data.columns) != list(new_data.columns):
            logger.warning(
                "Columnas diferentes entre train y new data. Usando interseccion."
            )
            common_cols = list(set(train_data.columns) & set(new_data.columns))
            train_data = train_data[common_cols]
            new_data = new_data[common_cols]

        drifted_features = []
        drift_details = {}

        # Aplicar KS test a cada feature
        for feature in train_data.columns:
            try:
                # Extraer valores (dropna para evitar errores)
                train_values = train_data[feature].dropna().values
                new_values = new_data[feature].dropna().values

                # KS test requiere al menos 2 valores en cada distribucion
                if len(train_values) < 2 or len(new_values) < 2:
                    continue

                # Aplicar KS test
                statistic, p_value = ks_2samp(train_values, new_values)

                drift_details[feature] = {
                    "statistic": float(statistic),
                    "p_value": float(p_value),
                    "has_drift": p_value < self.ks_threshold,
                }

                # Si p-value es bajo, hay drift significativo
                if p_value < self.ks_threshold:
                    drifted_features.append(feature)
                    logger.warning(
                        f"Drift detectado en '{feature}': "
                        f"KS={statistic:.4f}, p={p_value:.4f}"
                    )

            except Exception as e:
                logger.error(f"Error en KS test para '{feature}': {e}")
                continue

        has_drift = len(drifted_features) > 0

        logger.info(
            f"Data drift: {len(drifted_features)}/{len(train_data.columns)} "
            f"features con drift (p<{self.ks_threshold})"
        )

        return {
            "has_drift": has_drift,
            "drifted_features": drifted_features,
            "drift_details": drift_details,
            "threshold": self.ks_threshold,
        }

    # ============================================================
    # 2. CONCEPT DRIFT (degradacion de rendimiento del modelo)
    # ============================================================

    def detect_concept_drift(
        self,
        model,
        X_new: pd.DataFrame,
        y_new: pd.Series,
    ) -> Dict[str, any]:
        """
        Detecta concept drift evaluando el modelo en datos nuevos.

        Si el F1 score en datos nuevos cae por debajo del umbral,
        indica que la relacion X -> y ha cambiado (concept drift).

        Args:
            model: Modelo entrenado (con metodo predict()).
            X_new: Features de nuevos datos.
            y_new: Labels verdaderos de nuevos datos.

        Returns:
            Dict con:
            - has_drift (bool): True si F1 < threshold.
            - f1_score (float): F1 score en datos nuevos.
            - accuracy (float): Accuracy en datos nuevos.
            - threshold (float): Umbral usado.

        Ejemplo:
            >>> result = detector.detect_concept_drift(model, X_new, y_new)
            >>> if result["has_drift"]:
            ...     print(f"F1 score bajo: {result['f1_score']:.2f}")
        """
        logger.info(
            f"Detectando concept drift: {len(X_new)} muestras, threshold={self.f1_threshold}"
        )

        try:
            # Predecir en nuevos datos
            y_pred = model.predict(X_new)

            # Calcular metricas
            f1 = f1_score(y_new, y_pred, average="binary", zero_division=0)
            acc = accuracy_score(y_new, y_pred)

            has_drift = f1 < self.f1_threshold

            if has_drift:
                logger.warning(
                    f"Concept drift detectado: F1={f1:.3f} < {self.f1_threshold}"
                )
            else:
                logger.info(f"No concept drift: F1={f1:.3f} >= {self.f1_threshold}")

            return {
                "has_drift": has_drift,
                "f1_score": float(f1),
                "accuracy": float(acc),
                "threshold": self.f1_threshold,
            }

        except Exception as e:
            logger.error(f"Error detectando concept drift: {e}")
            return {
                "has_drift": False,
                "f1_score": None,
                "accuracy": None,
                "threshold": self.f1_threshold,
                "error": str(e),
            }

    # ============================================================
    # 3. VOLUME DRIFT (acumulacion de nuevos datos)
    # ============================================================

    def detect_volume_drift(
        self,
        train_size: int,
        new_size: int,
    ) -> Dict[str, any]:
        """
        Detecta volume drift basado en numero de nuevos datos.

        Si hay suficientes tokens nuevos etiquetados, vale la pena
        re-entrenar para incorporarlos al modelo.

        Args:
            train_size: Numero de tokens usados en entrenamiento original.
            new_size: Numero de tokens nuevos etiquetados desde entonces.

        Returns:
            Dict con:
            - has_drift (bool): True si new_size >= threshold.
            - new_tokens (int): Numero de tokens nuevos.
            - threshold (int): Umbral usado.

        Ejemplo:
            >>> result = detector.detect_volume_drift(100, 55)
            >>> if result["has_drift"]:
            ...     print(f"Hay {result['new_tokens']} tokens nuevos!")
        """
        has_drift = new_size >= self.volume_threshold

        if has_drift:
            logger.info(
                f"Volume drift detectado: {new_size} nuevos tokens "
                f">= {self.volume_threshold}"
            )
        else:
            logger.info(
                f"No volume drift: {new_size} nuevos tokens "
                f"< {self.volume_threshold}"
            )

        return {
            "has_drift": has_drift,
            "new_tokens": new_size,
            "train_tokens": train_size,
            "threshold": self.volume_threshold,
        }

    # ============================================================
    # 4. TIME DRIFT (tiempo desde ultimo entrenamiento)
    # ============================================================

    def detect_time_drift(
        self,
        last_train_date: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Detecta time drift basado en tiempo desde ultimo entrenamiento.

        Incluso si no hay drift estadistico, es buena practica re-entrenar
        periodicamente para incorporar datos recientes.

        Args:
            last_train_date: Fecha de ultimo entrenamiento (ISO format).
                             Si es None, asume que nunca se entreno.

        Returns:
            Dict con:
            - has_drift (bool): True si han pasado >= days_threshold.
            - days_since_training (int): Dias desde ultimo entrenamiento.
            - threshold (int): Umbral de dias.

        Ejemplo:
            >>> result = detector.detect_time_drift("2026-01-01T00:00:00Z")
            >>> if result["has_drift"]:
            ...     print(f"Hace {result['days_since_training']} dias!")
        """
        if last_train_date is None:
            logger.warning("No hay fecha de ultimo entrenamiento. Asumiendo drift.")
            return {
                "has_drift": True,
                "days_since_training": None,
                "threshold": self.days_threshold,
            }

        try:
            # Parsear fecha
            last_train = datetime.fromisoformat(last_train_date.replace("Z", "+00:00"))
            now = datetime.now(last_train.tzinfo)

            # Calcular dias transcurridos
            days_since = (now - last_train).days

            has_drift = days_since >= self.days_threshold

            if has_drift:
                logger.info(
                    f"Time drift detectado: {days_since} dias >= {self.days_threshold}"
                )
            else:
                logger.info(
                    f"No time drift: {days_since} dias < {self.days_threshold}"
                )

            return {
                "has_drift": has_drift,
                "days_since_training": days_since,
                "last_train_date": last_train_date,
                "threshold": self.days_threshold,
            }

        except Exception as e:
            logger.error(f"Error parseando fecha '{last_train_date}': {e}")
            return {
                "has_drift": True,  # Por seguridad, asumir drift
                "days_since_training": None,
                "threshold": self.days_threshold,
                "error": str(e),
            }

    # ============================================================
    # DETECCION COMPLETA (todos los tipos de drift)
    # ============================================================

    def detect_all_drift(
        self,
        train_data: Optional[pd.DataFrame] = None,
        new_data: Optional[pd.DataFrame] = None,
        model=None,
        y_new: Optional[pd.Series] = None,
        train_size: Optional[int] = None,
        new_size: Optional[int] = None,
        last_train_date: Optional[str] = None,
    ) -> Dict[str, any]:
        """
        Ejecuta todas las detecciones de drift y devuelve un reporte completo.

        Args:
            train_data: Features de entrenamiento (para data drift).
            new_data: Features nuevos (para data drift y concept drift).
            model: Modelo entrenado (para concept drift).
            y_new: Labels verdaderos de nuevos datos (para concept drift).
            train_size: Numero de tokens en entrenamiento (para volume drift).
            new_size: Numero de tokens nuevos (para volume drift).
            last_train_date: Fecha de ultimo entrenamiento (para time drift).

        Returns:
            Dict con:
            - needs_retraining (bool): True si alguna deteccion indica drift.
            - reasons (list): Lista de razones para re-entrenar.
            - data_drift (dict): Resultado de detect_data_drift().
            - concept_drift (dict): Resultado de detect_concept_drift().
            - volume_drift (dict): Resultado de detect_volume_drift().
            - time_drift (dict): Resultado de detect_time_drift().

        Ejemplo:
            >>> report = detector.detect_all_drift(
            ...     train_data=X_train,
            ...     new_data=X_new,
            ...     model=model,
            ...     y_new=y_new,
            ...     train_size=100,
            ...     new_size=55,
            ...     last_train_date="2026-01-01T00:00:00Z"
            ... )
            >>> if report["needs_retraining"]:
            ...     print(f"Re-entrenar por: {', '.join(report['reasons'])}")
        """
        logger.info("Iniciando deteccion completa de drift...")

        results = {}
        reasons = []

        # 1. Data Drift
        if train_data is not None and new_data is not None:
            results["data_drift"] = self.detect_data_drift(train_data, new_data)
            if results["data_drift"]["has_drift"]:
                reasons.append(
                    f"Data drift ({len(results['data_drift']['drifted_features'])} features)"
                )
        else:
            results["data_drift"] = {"has_drift": False, "skipped": True}

        # 2. Concept Drift
        if model is not None and new_data is not None and y_new is not None:
            results["concept_drift"] = self.detect_concept_drift(model, new_data, y_new)
            if results["concept_drift"]["has_drift"]:
                f1 = results["concept_drift"]["f1_score"]
                reasons.append(f"Concept drift (F1={f1:.2f})")
        else:
            results["concept_drift"] = {"has_drift": False, "skipped": True}

        # 3. Volume Drift
        if train_size is not None and new_size is not None:
            results["volume_drift"] = self.detect_volume_drift(train_size, new_size)
            if results["volume_drift"]["has_drift"]:
                reasons.append(
                    f"Volume drift ({results['volume_drift']['new_tokens']} nuevos tokens)"
                )
        else:
            results["volume_drift"] = {"has_drift": False, "skipped": True}

        # 4. Time Drift
        results["time_drift"] = self.detect_time_drift(last_train_date)
        if results["time_drift"]["has_drift"]:
            days = results["time_drift"]["days_since_training"]
            reasons.append(f"Time drift ({days} dias)" if days else "Time drift")

        # Decision final
        needs_retraining = len(reasons) > 0

        if needs_retraining:
            logger.warning(
                f"RE-ENTRENAMIENTO RECOMENDADO. Razones: {', '.join(reasons)}"
            )
        else:
            logger.info("No se detectó drift. Modelo actual es adecuado.")

        return {
            "needs_retraining": needs_retraining,
            "reasons": reasons,
            **results,
        }

    # ============================================================
    # 5. FEATURE DRIFT (cambio en medianas de features)
    # ============================================================

    @staticmethod
    def detect_feature_drift(
        train_medians: dict,
        current_medians: dict,
        threshold_pct: float = 0.50,
        min_drifted_ratio: float = 0.20,
    ) -> Dict[str, any]:
        """
        Detecta drift comparando medianas de features entre entrenamiento y datos actuales.

        Para cada feature calcula el desplazamiento relativo (shift) entre
        la mediana de entrenamiento y la mediana actual. Si mas de un porcentaje
        minimo de features tienen shift > threshold, se considera drift.

        Args:
            train_medians: Medianas de features en datos de entrenamiento.
                           Formato: {"feature_name": valor, ...}
            current_medians: Medianas de features en datos actuales.
            threshold_pct: Porcentaje de cambio para considerar drift en una
                           feature individual (0.50 = 50%).
            min_drifted_ratio: Proporcion minima de features con drift para
                               disparar la alerta (0.20 = 20%).

        Returns:
            Dict con:
            - triggered (bool): True si drifted_count/total > min_drifted_ratio.
            - total_features (int): Numero total de features evaluadas.
            - drifted_count (int): Numero de features con drift.
            - drifted_ratio (float): Proporcion de features con drift.
            - details (dict): Solo features con drift, cada una con train/current/shift_pct.

        Ejemplo:
            >>> result = DriftDetector.detect_feature_drift(
            ...     {"feat_a": 0.5, "feat_b": 1.0},
            ...     {"feat_a": 0.8, "feat_b": 1.1},
            ... )
            >>> if result["triggered"]:
            ...     print(f"{result['drifted_count']} features con drift")
        """
        # Usar solo features presentes en ambos diccionarios
        common_features = set(train_medians.keys()) & set(current_medians.keys())

        if not common_features:
            logger.warning("No hay features en comun para comparar medianas.")
            return {
                "triggered": False,
                "total_features": 0,
                "drifted_count": 0,
                "drifted_ratio": 0.0,
                "details": {},
            }

        drifted_details = {}

        for feat in sorted(common_features):
            train_val = train_medians[feat]
            current_val = current_medians[feat]

            # Calcular shift relativo: abs(current - train) / max(|train|, epsilon)
            denominator = max(abs(train_val), 1e-6)
            shift = abs(current_val - train_val) / denominator

            if shift > threshold_pct:
                drifted_details[feat] = {
                    "train": train_val,
                    "current": current_val,
                    "shift_pct": round(shift, 4),
                }

        total = len(common_features)
        drifted_count = len(drifted_details)
        drifted_ratio = drifted_count / total if total > 0 else 0.0
        triggered = drifted_ratio > min_drifted_ratio

        if triggered:
            logger.warning(
                f"Feature drift detectado: {drifted_count}/{total} features "
                f"({drifted_ratio:.1%}) superan umbral de {threshold_pct:.0%}"
            )
        else:
            logger.info(
                f"No feature drift: {drifted_count}/{total} features "
                f"({drifted_ratio:.1%}) con shift > {threshold_pct:.0%}"
            )

        return {
            "triggered": triggered,
            "total_features": total,
            "drifted_count": drifted_count,
            "drifted_ratio": round(drifted_ratio, 4),
            "details": drifted_details,
        }

    # ============================================================
    # 6. REPORTE COMPLETO (genera reporte plano para save_drift_report)
    # ============================================================

    @classmethod
    def generate_report(
        cls,
        model_version: str,
        metadata: dict,
        train_medians: dict,
        current_medians: dict,
        days_threshold: int = 30,
        volume_threshold: int = 50,
    ) -> dict:
        """
        Genera un reporte completo de drift listo para save_drift_report().

        Ejecuta las tres verificaciones ligeras (time, volume, feature) sin
        necesidad de datos crudos ni modelo cargado:
        - Time drift: compara metadata["trained_at"] con fecha actual.
        - Volume drift: consulta labels en storage vs metadata["train_size"].
        - Feature drift: compara train_medians vs current_medians.

        Args:
            model_version: Version del modelo (ej: "v12").
            metadata: Dict con "trained_at" (ISO string) y "train_size" (int).
            train_medians: Medianas de features usadas en entrenamiento.
            current_medians: Medianas de features actuales.
            days_threshold: Dias maximos sin re-entrenar (default: 30).
            volume_threshold: Tokens nuevos minimos para re-entrenar (default: 50).

        Returns:
            Dict plano con todos los campos necesarios para save_drift_report(),
            incluyendo: model_version, needs_retraining, reasons, scores
            individuales por tipo de drift, y overall_score ponderado.

        Ejemplo:
            >>> report = DriftDetector.generate_report(
            ...     "v12",
            ...     {"trained_at": "2026-03-01T00:00:00Z", "train_size": 1200},
            ...     {"feat_a": 0.5}, {"feat_a": 0.9}
            ... )
            >>> report["needs_retraining"]
            True
        """
        # Crear instancia temporal con los umbrales proporcionados
        detector = cls(days_threshold=days_threshold, volume_threshold=volume_threshold)
        reasons = []

        # --- 1. Time drift ---
        trained_at = metadata.get("trained_at")
        time_result = detector.detect_time_drift(trained_at)
        time_days = time_result.get("days_since_training")
        time_triggered = time_result["has_drift"]
        if time_triggered:
            reasons.append("time_drift")

        # --- 2. Volume drift ---
        # Consultar cuantos labels hay actualmente en storage
        train_size = metadata.get("train_size", 0)
        new_labels = 0
        try:
            from src.data.supabase_storage import get_storage
            storage = get_storage()
            rows = storage.query("SELECT COUNT(*) as cnt FROM labels")
            total_labels = rows[0]["cnt"] if rows else 0
            new_labels = max(0, total_labels - train_size)
        except Exception as e:
            logger.warning(f"No se pudo consultar labels en storage: {e}")
            total_labels = train_size  # Asumir sin cambios si falla

        volume_result = detector.detect_volume_drift(train_size, new_labels)
        volume_triggered = volume_result["has_drift"]
        if volume_triggered:
            reasons.append("volume_drift")

        # --- 3. Feature drift ---
        feature_result = cls.detect_feature_drift(train_medians, current_medians)
        feature_triggered = feature_result["triggered"]
        if feature_triggered:
            reasons.append("feature_drift")

        # --- Overall score (0-1, ponderado) ---
        # Pesos: time=0.3, volume=0.3, feature=0.4
        time_score = 1.0 if time_triggered else (
            min((time_days or 0) / days_threshold, 1.0)
        )
        volume_score = 1.0 if volume_triggered else (
            min(new_labels / max(volume_threshold, 1), 1.0)
        )
        feature_score = feature_result["drifted_ratio"]

        overall_score = round(
            0.3 * time_score + 0.3 * volume_score + 0.4 * feature_score, 4
        )

        needs_retraining = len(reasons) > 0

        # Reporte completo (estructura interna para referencia)
        full_report = {
            "time_drift": time_result,
            "volume_drift": volume_result,
            "feature_drift": feature_result,
        }

        # Top features con drift (limitar details para no saturar la DB)
        feature_details = feature_result.get("details", {})
        # Ordenar por shift descendente y tomar top 10
        sorted_details = dict(
            sorted(
                feature_details.items(),
                key=lambda x: x[1]["shift_pct"],
                reverse=True,
            )[:10]
        )

        if needs_retraining:
            logger.warning(
                f"Reporte {model_version}: RE-ENTRENAMIENTO RECOMENDADO. "
                f"Razones: {reasons}. Score: {overall_score}"
            )
        else:
            logger.info(
                f"Reporte {model_version}: modelo OK. Score: {overall_score}"
            )

        return {
            "model_version": model_version,
            "needs_retraining": needs_retraining,
            "reasons": reasons,
            "time_drift_days": time_days,
            "time_drift_triggered": time_triggered,
            "volume_drift_new_labels": new_labels,
            "volume_drift_triggered": volume_triggered,
            "feature_drift_count": feature_result["drifted_count"],
            "feature_drift_total": feature_result["total_features"],
            "feature_drift_triggered": feature_triggered,
            "feature_drift_details": sorted_details,
            "overall_score": overall_score,
            "report_json": full_report,
        }

    # ============================================================
    # 7. CARGA DE ARTEFACTOS DESDE DISCO LOCAL
    # ============================================================

    @staticmethod
    def load_from_local(model_version: str = None) -> Tuple[dict, dict]:
        """
        Carga metadata.json y train_medians.json desde disco local.

        Lee los archivos del directorio data/models/{version}/.
        Si no se especifica version, lee latest_version.txt para determinarla.
        Los archivos deben existir localmente (descargados por download_models.py
        o generados por el pipeline de entrenamiento).

        Args:
            model_version: Version del modelo (ej: "v12"). Si es None,
                           lee latest_version.txt de MODELS_DIR.

        Returns:
            Tupla (metadata, train_medians) donde:
            - metadata: dict con "trained_at", "train_size", etc.
            - train_medians: dict con medianas por feature.

        Raises:
            FileNotFoundError: Si los archivos no existen en disco.

        Ejemplo:
            >>> metadata, medians = DriftDetector.load_from_local("v12")
            >>> print(metadata["trained_at"])
            "2026-03-15T10:30:00Z"
        """
        from config import MODELS_DIR

        # Determinar version si no se proporciona
        if model_version is None:
            version_file = MODELS_DIR / "latest_version.txt"
            if version_file.exists():
                model_version = version_file.read_text().strip()
                logger.info(f"Version detectada desde latest_version.txt: {model_version}")
            else:
                raise FileNotFoundError(
                    f"No se encontro latest_version.txt en {MODELS_DIR}. "
                    "Especifica model_version manualmente."
                )

        version_dir = MODELS_DIR / model_version

        # Cargar metadata.json
        metadata_path = version_dir / "metadata.json"
        if not metadata_path.exists():
            raise FileNotFoundError(
                f"No se encontro metadata.json en {version_dir}. "
                "Ejecuta download_models.py o el pipeline de entrenamiento primero."
            )
        with open(metadata_path, "r") as f:
            metadata = json.load(f)

        # Cargar train_medians.json
        medians_path = version_dir / "train_medians.json"
        if not medians_path.exists():
            raise FileNotFoundError(
                f"No se encontro train_medians.json en {version_dir}. "
                "Ejecuta download_models.py o el pipeline de entrenamiento primero."
            )
        with open(medians_path, "r") as f:
            train_medians = json.load(f)

        logger.info(
            f"Artefactos {model_version} cargados: "
            f"metadata ({len(metadata)} campos), "
            f"train_medians ({len(train_medians)} features)"
        )

        return metadata, train_medians
