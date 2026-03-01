"""
Modulos de extraccion de features.

Cada modulo calcula un grupo de features especifico:
    - tokenomics: Distribucion de holders, concentracion
    - liquidity: Liquidez del pool, crecimiento, estabilidad
    - price_action: Retornos, volatilidad, tendencias de volumen
    - social: Compradores, vendedores, actividad de trading
    - contract: Verificacion, ownership, edad del contrato
    - market_context: Estado del mercado al momento del lanzamiento
    - builder: Orquestador que combina todos los modulos
"""

from .builder import FeatureBuilder
from .tokenomics import compute_tokenomics_features
from .liquidity import compute_liquidity_features
from .price_action import compute_price_action_features
from .social import compute_social_features
from .contract import compute_contract_features
from .market_context import compute_market_context_features

__all__ = [
    "FeatureBuilder",
    "compute_tokenomics_features",
    "compute_liquidity_features",
    "compute_price_action_features",
    "compute_social_features",
    "compute_contract_features",
    "compute_market_context_features",
]
