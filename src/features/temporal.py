"""
temporal.py - Features temporales del lanzamiento de un token.

Features basados en el timing del lanzamiento:
- Dia de la semana
- Hora del dia (UTC)
- Dias desde lanzamiento
- Si fue lanzado en fin de semana

Hipotesis: Los tokens lanzados en ciertos momentos pueden tener
diferente performance (ej: tokens lanzados viernes tarde pueden
tener peor rendimiento por menor atencion del mercado).
"""

from datetime import datetime, timezone
from typing import Dict, Any

from src.utils.logger import get_logger

logger = get_logger(__name__)


def extract_temporal_features(
    token_data: Dict[str, Any],
    current_time: datetime = None,
) -> Dict[str, Any]:
    """
    Extrae features temporales del lanzamiento de un token.

    Args:
        token_data: Dict con informacion del token.
            Requiere: 'created_at' (timestamp ISO 8601)
        current_time: Timestamp actual para calcular dias desde lanzamiento.
            Si no se pasa, usa datetime.now(timezone.utc).

    Returns:
        Dict con features temporales:
        - launch_day_of_week: 0=Lunes, 6=Domingo
        - launch_hour_utc: Hora del dia en UTC (0-23)
        - launch_is_weekend: 1 si sabado/domingo, 0 si no
        - days_since_launch: Dias desde el lanzamiento
        - launch_hour_category: early_morning/morning/afternoon/evening/night

    Ejemplo:
        features = extract_temporal_features({
            "created_at": "2026-02-26T15:30:00Z"
        })
        # {
        #     "launch_day_of_week": 2,  # Miercoles
        #     "launch_hour_utc": 15,
        #     "launch_is_weekend": 0,
        #     "days_since_launch": 1,
        #     "launch_hour_category": "afternoon"
        # }
    """
    features = {}

    # Validar que tenemos created_at
    created_at_str = token_data.get("created_at")
    if not created_at_str:
        logger.warning("No hay 'created_at' en token_data, features temporales = None")
        return {
            "launch_day_of_week": None,
            "launch_hour_utc": None,
            "launch_is_weekend": None,
            "days_since_launch": None,
            "launch_hour_category": None,
        }

    try:
        # Parsear timestamp
        # Formato esperado: "2026-02-26T15:30:00Z" o "2026-02-26T15:30:00+00:00"
        if created_at_str.endswith("Z"):
            created_at_str = created_at_str[:-1] + "+00:00"

        created_at = datetime.fromisoformat(created_at_str)

        # Asegurar que tiene timezone
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        # Current time (para dias desde lanzamiento)
        if current_time is None:
            current_time = datetime.now(timezone.utc)
        elif current_time.tzinfo is None:
            current_time = current_time.replace(tzinfo=timezone.utc)

        # ============================================================
        # FEATURE 1: Dia de la semana (0=Lunes, 6=Domingo)
        # ============================================================
        features["launch_day_of_week"] = created_at.weekday()

        # ============================================================
        # FEATURE 2: Hora del dia en UTC (0-23)
        # ============================================================
        features["launch_hour_utc"] = created_at.hour

        # ============================================================
        # FEATURE 3: Es fin de semana? (Sabado=5, Domingo=6)
        # ============================================================
        features["launch_is_weekend"] = int(created_at.weekday() >= 5)

        # ============================================================
        # FEATURE 4: Dias desde lanzamiento
        # ============================================================
        delta = current_time - created_at
        features["days_since_launch"] = delta.days + (delta.seconds / 86400)

        # ============================================================
        # FEATURE 5: Categoria de hora del dia
        # ============================================================
        # early_morning: 0-5
        # morning: 6-11
        # afternoon: 12-17
        # evening: 18-21
        # night: 22-23
        hour = created_at.hour
        if 0 <= hour < 6:
            features["launch_hour_category"] = "early_morning"
        elif 6 <= hour < 12:
            features["launch_hour_category"] = "morning"
        elif 12 <= hour < 18:
            features["launch_hour_category"] = "afternoon"
        elif 18 <= hour < 22:
            features["launch_hour_category"] = "evening"
        else:
            features["launch_hour_category"] = "night"

    except Exception as e:
        logger.error(f"Error parseando created_at '{created_at_str}': {e}")
        features = {
            "launch_day_of_week": None,
            "launch_hour_utc": None,
            "launch_is_weekend": None,
            "days_since_launch": None,
            "launch_hour_category": None,
        }

    return features


def get_temporal_features_for_batch(tokens: list, current_time: datetime = None) -> Dict[str, Dict]:
    """
    Extrae features temporales para multiples tokens.

    Args:
        tokens: Lista de dicts con informacion de tokens.
        current_time: Timestamp actual (opcional).

    Returns:
        Dict con token_id como key y features como value.

    Ejemplo:
        features_dict = get_temporal_features_for_batch([
            {"token_id": "abc123", "created_at": "2026-02-26T15:30:00Z"},
            {"token_id": "def456", "created_at": "2026-02-25T08:00:00Z"},
        ])
    """
    features_dict = {}

    for token in tokens:
        token_id = token.get("token_id")
        if not token_id:
            continue

        features = extract_temporal_features(token, current_time)
        features_dict[token_id] = features

    return features_dict


# ============================================================
# INTERPRETACION DE FEATURES
# ============================================================

def interpret_day_of_week(day: int) -> str:
    """Convierte numero de dia a nombre."""
    days = ["Lunes", "Martes", "Miercoles", "Jueves", "Viernes", "Sabado", "Domingo"]
    return days[day] if 0 <= day <= 6 else "Unknown"


def interpret_hour_category(category: str) -> str:
    """Descripcion legible de categoria de hora."""
    descriptions = {
        "early_morning": "Madrugada (0-5 UTC)",
        "morning": "Mañana (6-11 UTC)",
        "afternoon": "Tarde (12-17 UTC)",
        "evening": "Noche (18-21 UTC)",
        "night": "Noche tardía (22-23 UTC)",
    }
    return descriptions.get(category, "Unknown")


if __name__ == "__main__":
    # Test rapido
    test_token = {
        "token_id": "test123",
        "created_at": "2026-02-26T15:30:00Z",  # Miercoles, 3:30 PM UTC
    }

    features = extract_temporal_features(test_token)
    print("Features Temporales:")
    print(f"  Dia de la semana: {features['launch_day_of_week']} ({interpret_day_of_week(features['launch_day_of_week'])})")
    print(f"  Hora UTC: {features['launch_hour_utc']}")
    print(f"  Es fin de semana: {features['launch_is_weekend']}")
    print(f"  Dias desde lanzamiento: {features['days_since_launch']:.2f}")
    print(f"  Categoria hora: {features['launch_hour_category']} ({interpret_hour_category(features['launch_hour_category'])})")
