"""
backtester.py - Backtesting de predicciones sobre tokens historicos.

Simula predicciones en tokens con resultado conocido para medir
la efectividad real del modelo. Responde la pregunta:

"Si hubieramos usado este modelo hace 30 dias, cuantos gems
habria detectado y cuantas alertas falsas habria generado?"

Clase:
    Backtester: Backtesting con metricas de precision y rentabilidad.

Uso:
    from src.models.backtester import Backtester

    bt = Backtester()
    results = bt.backtest_historical()
    print(f"Precision: {results['precision']:.1%}")
    print(f"Rentabilidad simulada: {results['simulated_return']:.1%}")
"""

import json
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd

from src.data.supabase_storage import get_storage
from src.models.scorer import GemScorer
from src.utils.logger import get_logger
from src.utils.helpers import safe_divide

try:
    from config import MODELS_DIR
except ImportError:
    MODELS_DIR = Path("data/models")

logger = get_logger(__name__)


class Backtester:
    """
    Backtesting de senales de gem sobre datos historicos.

    Usa tokens con label conocido (gem, failure, etc.) para simular
    que pasaria si se hubieran seguido las senales del modelo.

    Metricas calculadas:
    - Precision: De las senales STRONG, cuantas eran gems reales.
    - Recall: De los gems reales, cuantos se detectaron.
    - Falsos positivos: Senales que no eran gems.
    - Rentabilidad simulada: Retorno promedio de tokens con senal.

    Args:
        storage: Instancia de Storage.
        scorer: Instancia de GemScorer (si None, crea una nueva).

    Ejemplo:
        bt = Backtester()
        results = bt.backtest_historical()
        print(results["summary"])
    """

    def __init__(
        self,
        storage=None,
        scorer: Optional[GemScorer] = None,
    ):
        self.storage = storage or get_storage()
        self.scorer = scorer or GemScorer(storage=self.storage)

    # ============================================================
    # BACKTEST SOBRE TOKENS HISTORICOS
    # ============================================================

    def load_train_tokens(self, models_dir: Optional[Path] = None) -> list:
        """
        Lee train_token_ids del metadata.json mas reciente.

        Args:
            models_dir: Directorio de modelos. Por defecto usa MODELS_DIR.

        Returns:
            Lista de token_ids usados en entrenamiento, o lista vacia.
        """
        base_dir = Path(models_dir) if models_dir else MODELS_DIR

        # Intentar leer la version mas reciente
        latest_file = base_dir / "latest_version.txt"
        if latest_file.exists():
            version = latest_file.read_text().strip()
            metadata_path = base_dir / version / "metadata.json"
            if metadata_path.exists():
                with open(metadata_path) as f:
                    metadata = json.load(f)
                token_ids = metadata.get("train_token_ids", [])
                if token_ids:
                    logger.info(f"Cargados {len(token_ids)} train_token_ids de {version}")
                return token_ids

        logger.info("No se encontraron train_token_ids en metadata")
        return []

    def backtest_historical(
        self,
        signal_threshold: str = "MEDIUM",
        exclude_tokens: Optional[list] = None,
    ) -> dict:
        """
        Ejecuta backtesting sobre todos los tokens con label conocido.

        Para cada token con label:
        1. Calcula la probabilidad de gem del modelo.
        2. Compara la senal con el resultado real.
        3. Calcula metricas agregadas.

        IMPORTANTE: Por defecto excluye tokens usados en entrenamiento
        para evitar data leakage (metricas optimistamente sesgadas).

        Args:
            signal_threshold: Nivel minimo de senal para considerar
                como "candidato". Opciones: STRONG, MEDIUM, WEAK.
            exclude_tokens: Lista de token_ids a excluir del backtest.
                Si es None, auto-carga los train_token_ids del metadata.

        Returns:
            Dict con:
            - total_tokens: int
            - total_signaled: int (tokens con senal >= threshold)
            - true_positives: int (senales que eran gems reales)
            - false_positives: int (senales que no eran gems)
            - false_negatives: int (gems no detectados)
            - precision: float (true_pos / signaled)
            - recall: float (true_pos / total_gems)
            - simulated_return: float (retorno promedio de tokens con senal)
            - details: DataFrame con prediccion por token
            - summary: str (resumen legible)
        """
        logger.info(f"Ejecutando backtest (threshold={signal_threshold})...")

        # Auto-cargar tokens de entrenamiento si no se proporcionaron
        if exclude_tokens is None:
            exclude_tokens = self.load_train_tokens()

        # Obtener tokens con label
        labels_df = self.storage.query("""
            SELECT l.token_id, l.label_multi, l.label_binary,
                   l.max_multiple, l.final_multiple,
                   t.chain, t.symbol
            FROM labels l
            INNER JOIN tokens t ON l.token_id = t.token_id
        """)

        if labels_df.empty:
            logger.warning("No hay tokens con labels para backtesting")
            return {"error": "Sin datos de labels"}

        # Filtrar tokens de entrenamiento si se proporcionaron
        if exclude_tokens:
            antes = len(labels_df)
            labels_df = labels_df[~labels_df["token_id"].isin(exclude_tokens)]
            excluidos = antes - len(labels_df)
            logger.info(f"Excluidos {excluidos} tokens de entrenamiento del backtest")

        if labels_df.empty:
            logger.warning("No quedan tokens despues de excluir los de entrenamiento")
            return {"error": "Sin datos despues de excluir tokens de entrenamiento"}

        logger.info(f"Tokens con label: {len(labels_df)}")

        # Definir umbral de probabilidad segun nivel de senal
        from src.models.scorer import SIGNAL_THRESHOLDS
        prob_threshold = SIGNAL_THRESHOLDS.get(signal_threshold, 0.65)

        # Calificar cada token
        results = []
        for _, row in labels_df.iterrows():
            token_id = row["token_id"]
            try:
                score = self.scorer.score_token(token_id)
                results.append({
                    "token_id": token_id,
                    "chain": row["chain"],
                    "symbol": row.get("symbol", ""),
                    "probability": score["probability"],
                    "signal": score["signal"],
                    "signaled": score["probability"] >= prob_threshold,
                    "label_real": row["label_multi"],
                    "is_gem_real": row["label_binary"] == 1,
                    "max_multiple": row["max_multiple"],
                    "final_multiple": row["final_multiple"],
                })
            except Exception as e:
                logger.warning(f"Error scoring {token_id[:10]}: {e}")

        if not results:
            return {"error": "No se pudo calificar ningun token"}

        df = pd.DataFrame(results)

        # Calcular metricas
        total = len(df)
        signaled = df["signaled"].sum()
        gems_reales = df["is_gem_real"].sum()

        # True positives: senal positiva Y es gem real
        tp = ((df["signaled"]) & (df["is_gem_real"])).sum()
        # False positives: senal positiva PERO no es gem
        fp = ((df["signaled"]) & (~df["is_gem_real"])).sum()
        # False negatives: gem real PERO sin senal
        fn = ((~df["signaled"]) & (df["is_gem_real"])).sum()
        # True negatives: sin senal Y no es gem
        tn = ((~df["signaled"]) & (~df["is_gem_real"])).sum()

        precision = safe_divide(tp, tp + fp, default=0.0)
        recall = safe_divide(tp, tp + fn, default=0.0)
        f1 = safe_divide(2 * precision * recall, precision + recall, default=0.0)

        # Rentabilidad simulada: promedio de max_multiple de tokens con senal
        signaled_tokens = df[df["signaled"]]
        if not signaled_tokens.empty:
            avg_return = signaled_tokens["max_multiple"].mean()
            median_return = signaled_tokens["max_multiple"].median()
        else:
            avg_return = 0.0
            median_return = 0.0

        # Resumen legible
        summary = (
            f"BACKTEST RESULTS (threshold={signal_threshold}, "
            f"prob>={prob_threshold:.0%})\n"
            f"{'='*50}\n"
            f"Total tokens evaluados:    {total}\n"
            f"Gems reales:               {int(gems_reales)}\n"
            f"Tokens con senal:          {int(signaled)}\n"
            f"  - True positives (gems detectados):  {int(tp)}\n"
            f"  - False positives (alertas falsas):   {int(fp)}\n"
            f"  - False negatives (gems perdidos):    {int(fn)}\n"
            f"  - True negatives (correctos):         {int(tn)}\n"
            f"{'='*50}\n"
            f"Precision:  {precision:.1%}  "
            f"(de las senales, cuantas eran gems)\n"
            f"Recall:     {recall:.1%}  "
            f"(de los gems, cuantos se detectaron)\n"
            f"F1:         {f1:.4f}\n"
            f"{'='*50}\n"
            f"Rentabilidad de tokens con senal:\n"
            f"  Promedio max_multiple: {avg_return:.2f}x\n"
            f"  Mediana max_multiple:  {median_return:.2f}x\n"
        )

        logger.info(f"\n{summary}")

        return {
            "total_tokens": total,
            "total_gems": int(gems_reales),
            "total_signaled": int(signaled),
            "true_positives": int(tp),
            "false_positives": int(fp),
            "false_negatives": int(fn),
            "true_negatives": int(tn),
            "precision": float(precision),
            "recall": float(recall),
            "f1": float(f1),
            "avg_return": float(avg_return),
            "median_return": float(median_return),
            "signal_threshold": signal_threshold,
            "prob_threshold": float(prob_threshold),
            "details": df,
            "summary": summary,
        }

    # ============================================================
    # COMPARAR MULTIPLES THRESHOLDS
    # ============================================================

    def compare_thresholds(self) -> pd.DataFrame:
        """
        Compara resultados de backtest con diferentes niveles de senal.

        Returns:
            DataFrame con precision, recall, F1 para cada threshold.
        """
        logger.info("Comparando thresholds de senal...")

        rows = []
        for threshold in ["STRONG", "MEDIUM", "WEAK"]:
            try:
                result = self.backtest_historical(signal_threshold=threshold)
                if "error" not in result:
                    rows.append({
                        "threshold": threshold,
                        "prob_min": result["prob_threshold"],
                        "signaled": result["total_signaled"],
                        "precision": result["precision"],
                        "recall": result["recall"],
                        "f1": result["f1"],
                        "avg_return": result["avg_return"],
                    })
            except Exception as e:
                logger.error(f"Error con threshold {threshold}: {e}")

        df = pd.DataFrame(rows)
        if not df.empty:
            logger.info(f"\n{df.to_string(index=False)}")

        return df
