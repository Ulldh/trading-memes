"""
test_config.py - Tests de configuracion y proteccion contra target leakage.
"""


def test_excluded_features_contains_leakage_features():
    """Verifica que features con target leakage estan en EXCLUDED_FEATURES."""
    from config import EXCLUDED_FEATURES
    leakage_features = [
        "max_return_7d", "return_7d", "close_to_high_ratio_7d",
        "price_recovery_ratio", "max_return_30d"
    ]
    for f in leakage_features:
        assert f in EXCLUDED_FEATURES, f"LEAKAGE RISK: {f} no esta en EXCLUDED_FEATURES"
