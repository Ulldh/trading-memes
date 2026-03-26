"""
regularization.py - Hiperparametros optimizados para reducir overfitting.

Los modelos v12 muestran overfitting, especialmente XGBoost:
- XGB: CV_F1=0.726 pero Val_F1=0.595 (gap de 0.131)
- RF:  CV_F1=0.671 y Val_F1=0.667 (gap de 0.004, OK)

El overfitting en XGBoost se debe a hiperparametros demasiado permisivos
que permiten al modelo memorizar patrones del set de entrenamiento
(especialmente con solo ~1467 muestras y 57 features).

Este modulo proporciona configuraciones regularizadas que:
1. Limitan la complejidad del arbol (max_depth, min_child_weight, gamma).
2. Introducen aleatoriedad (subsample, colsample_bytree).
3. Penalizan pesos extremos (reg_alpha L1, reg_lambda L2).
4. Reducen el learning rate (mas arboles, convergencia mas lenta pero estable).

Uso:
    from src.models.regularization import (
        get_regularized_xgb_params,
        get_regularized_rf_params,
    )

    # Obtener hiperparametros anti-overfitting
    xgb_params = get_regularized_xgb_params()
    rf_params = get_regularized_rf_params()

    # Usar directamente con los modelos
    xgb_model = XGBClassifier(**xgb_params)
    rf_model = RandomForestClassifier(**rf_params)

Funciones:
    get_regularized_xgb_params: Hiperparametros XGBoost con regularizacion fuerte.
    get_regularized_rf_params: Hiperparametros RF optimizados para generalizacion.
    get_conservative_xgb_params: Variante aun mas conservadora para datasets pequenos.
    compare_params: Compara parametros actuales vs regularizados.
"""

from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_regularized_xgb_params(random_seed: int = 42) -> dict:
    """
    Hiperparametros XGBoost con regularizacion anti-overfitting.

    Cambios respecto a v12 (config.py ML_CONFIG['xgb_params']):
    - max_depth: 6 -> 4 (arboles menos profundos = menos memorizar)
    - min_child_weight: 1 -> 5 (cada hoja necesita mas muestras)
    - gamma: 0 -> 0.2 (poda agresiva de splits no significativos)
    - subsample: 0.8 -> 0.8 (sin cambio, ya estaba bien)
    - colsample_bytree: 0.8 -> 0.8 (sin cambio)
    - reg_alpha: 0 -> 0.1 (regularizacion L1, promueve sparsity)
    - reg_lambda: 1 -> 1.5 (regularizacion L2 mas fuerte)
    - learning_rate: 0.05 -> 0.05 (sin cambio, ya estaba bien)
    - n_estimators: 500 -> 500 (sin cambio, early stopping decide)
    - early_stopping_rounds: 50 -> 50 (sin cambio)

    Nota: scale_pos_weight se calcula dinamicamente en trainer.py
    segun el ratio de clases, no se incluye aqui.

    Args:
        random_seed: Semilla para reproducibilidad (default 42).

    Returns:
        Diccionario con hiperparametros listo para XGBClassifier(**params).
    """
    params = {
        # --- Estructura del arbol ---
        "max_depth": 4,              # Limitar profundidad (v12: 6, default: 6)
        "min_child_weight": 5,       # Minimo de muestras por hoja (v12: 1 default)
        "gamma": 0.2,                # Poda: ganancia minima para split (v12: 0 default)

        # --- Subsampling (aleatoriedad) ---
        "subsample": 0.8,            # Fraccion de muestras por arbol (v12: 0.8)
        "colsample_bytree": 0.8,     # Fraccion de features por arbol (v12: 0.8)

        # --- Regularizacion ---
        "reg_alpha": 0.1,            # L1 regularizacion (v12: 0 default)
        "reg_lambda": 1.5,           # L2 regularizacion (v12: 1 default)

        # --- Learning rate y arboles ---
        "learning_rate": 0.05,       # Mas lento = mejor generalizacion (v12: 0.05)
        "n_estimators": 500,         # Max arboles, early stopping decide (v12: 500)

        # --- Early stopping ---
        "early_stopping_rounds": 50, # Parar si no mejora en 50 rondas (v12: 50)
        "eval_metric": "logloss",    # Metrica para early stopping (v12: logloss)

        # --- Reproducibilidad ---
        "random_state": random_seed,
        "n_jobs": -1,                # Usar todos los cores

        # --- GPU/CPU ---
        "tree_method": "hist",       # Metodo rapido para CPU
    }

    logger.info(
        f"XGBoost regularizado: max_depth={params['max_depth']}, "
        f"min_child_weight={params['min_child_weight']}, "
        f"gamma={params['gamma']}, "
        f"reg_alpha={params['reg_alpha']}, "
        f"reg_lambda={params['reg_lambda']}"
    )

    return params


def get_regularized_rf_params(random_seed: int = 42) -> dict:
    """
    Hiperparametros Random Forest optimizados para generalizacion.

    RF v12 ya generaliza bien (CV_F1=0.671, Val_F1=0.667), pero
    podemos mejorar ligeramente limitando la complejidad.

    Cambios respecto a v12 (config.py ML_CONFIG['rf_params']):
    - max_depth: 15 -> 10 (arboles menos profundos)
    - min_samples_split: 2 -> 10 (necesita mas muestras para dividir un nodo)
    - min_samples_leaf: 5 -> 5 (sin cambio, ya estaba bien)
    - max_features: None -> 'sqrt' (solo sqrt(n_features) por split)
    - n_estimators: 300 -> 300 (sin cambio)
    - class_weight: 'balanced' -> 'balanced' (sin cambio)

    Args:
        random_seed: Semilla para reproducibilidad (default 42).

    Returns:
        Diccionario con hiperparametros listo para RandomForestClassifier(**params).
    """
    params = {
        # --- Estructura del arbol ---
        "max_depth": 10,             # Limitar profundidad (v12: 15)
        "min_samples_split": 10,     # Minimo muestras para dividir nodo (v12: 2 default)
        "min_samples_leaf": 5,       # Minimo muestras por hoja (v12: 5)
        "max_features": "sqrt",      # Features por split: sqrt(n) (v12: None)

        # --- Ensemble ---
        "n_estimators": 300,         # Numero de arboles (v12: 300)

        # --- Balanceo de clases ---
        "class_weight": "balanced",  # Pesar clases inversamente a frecuencia (v12: balanced)

        # --- Reproducibilidad ---
        "random_state": random_seed,
        "n_jobs": -1,                # Usar todos los cores
    }

    logger.info(
        f"RF regularizado: max_depth={params['max_depth']}, "
        f"min_samples_split={params['min_samples_split']}, "
        f"max_features={params['max_features']}"
    )

    return params


def get_conservative_xgb_params(random_seed: int = 42) -> dict:
    """
    Variante ultra-conservadora de XGBoost para datasets muy pequenos.

    Para cuando el dataset tiene <2000 muestras y el overfitting es severo.
    Usa restricciones aun mas fuertes que get_regularized_xgb_params().

    Diferencias clave vs regularizado:
    - max_depth: 4 -> 3
    - min_child_weight: 5 -> 10
    - gamma: 0.2 -> 0.5
    - subsample: 0.8 -> 0.7
    - colsample_bytree: 0.8 -> 0.6
    - reg_alpha: 0.1 -> 0.5
    - reg_lambda: 1.5 -> 3.0

    Args:
        random_seed: Semilla para reproducibilidad (default 42).

    Returns:
        Diccionario con hiperparametros ultra-conservadores.
    """
    params = {
        "max_depth": 3,
        "min_child_weight": 10,
        "gamma": 0.5,
        "subsample": 0.7,
        "colsample_bytree": 0.6,
        "reg_alpha": 0.5,
        "reg_lambda": 3.0,
        "learning_rate": 0.03,
        "n_estimators": 800,
        "early_stopping_rounds": 75,
        "eval_metric": "logloss",
        "random_state": random_seed,
        "n_jobs": -1,
        "tree_method": "hist",
    }

    logger.info(
        f"XGBoost CONSERVADOR: max_depth={params['max_depth']}, "
        f"min_child_weight={params['min_child_weight']}, "
        f"gamma={params['gamma']}, "
        f"reg_alpha={params['reg_alpha']}, "
        f"reg_lambda={params['reg_lambda']}"
    )

    return params


def compare_params(current: dict, proposed: dict) -> dict:
    """
    Compara parametros actuales vs propuestos, mostrando las diferencias.

    Util para entender que cambia entre configuraciones y por que.

    Args:
        current: Diccionario de hiperparametros actuales.
        proposed: Diccionario de hiperparametros propuestos.

    Returns:
        Diccionario con las diferencias:
        {param_name: {"current": value, "proposed": value, "changed": bool}}
    """
    all_keys = set(list(current.keys()) + list(proposed.keys()))
    comparison = {}

    for key in sorted(all_keys):
        curr_val = current.get(key, "N/A")
        prop_val = proposed.get(key, "N/A")
        changed = curr_val != prop_val

        comparison[key] = {
            "current": curr_val,
            "proposed": prop_val,
            "changed": changed,
        }

        if changed:
            logger.info(f"  {key}: {curr_val} -> {prop_val}")

    n_changed = sum(1 for v in comparison.values() if v["changed"])
    logger.info(f"Total: {n_changed} parametros cambiados de {len(all_keys)}")

    return comparison
