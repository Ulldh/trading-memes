"""Pipeline de Machine Learning."""

from .labeler import Labeler
from .evaluator import ModelEvaluator


def __getattr__(name):
    """Lazy import para modulos con dependencias pesadas (xgboost, shap)."""
    if name == "ModelTrainer":
        from .trainer import ModelTrainer
        return ModelTrainer
    if name == "SHAPExplainer":
        from .explainer import SHAPExplainer
        return SHAPExplainer
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


__all__ = ["Labeler", "ModelTrainer", "ModelEvaluator", "SHAPExplainer"]
