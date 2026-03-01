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

import numpy as np
import pandas as pd
from pathlib import Path
from typing import Optional, Dict, Tuple
from datetime import datetime, timedelta

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
