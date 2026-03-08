"""
test_features.py - Tests para los modulos de feature engineering.

Ejecutar con: pytest tests/test_features.py -v

Verifican que cada modulo de features:
1. Calcula features correctamente con datos validos
2. Maneja datos faltantes/vacios sin crashear
3. Devuelve el tipo de dato correcto (dict)
"""

import sys
from pathlib import Path

import pytest
import pandas as pd
import numpy as np

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.features.tokenomics import compute_tokenomics_features, compute_whale_movement_features
from src.features.liquidity import compute_liquidity_features
from src.features.price_action import compute_price_action_features
from src.features.social import compute_social_features, compute_temporal_social_features
from src.features.contract import compute_contract_features, compute_contract_risk_features
from src.features.volatility_advanced import compute_volatility_advanced_features
from src.features.sentiment import compute_sentiment_features
from src.utils.helpers import safe_divide, pct_change, safe_float, detect_chain


# ============================================================
# Tests para helpers
# ============================================================

class TestHelpers:
    """Tests para funciones helper."""

    def test_safe_divide_normal(self):
        assert safe_divide(10, 2) == 5.0

    def test_safe_divide_by_zero(self):
        assert safe_divide(10, 0) == 0.0

    def test_safe_divide_by_none(self):
        assert safe_divide(10, None) == 0.0

    def test_pct_change_increase(self):
        assert pct_change(100, 150) == 0.5

    def test_pct_change_decrease(self):
        assert pct_change(100, 50) == -0.5

    def test_pct_change_zero_base(self):
        assert pct_change(0, 100) is None

    def test_safe_float_valid(self):
        assert safe_float("3.14") == 3.14

    def test_safe_float_none(self):
        assert safe_float(None) == 0.0

    def test_safe_float_invalid(self):
        assert safe_float("not_a_number") == 0.0

    def test_detect_chain_solana(self):
        """Detecta direccion Solana (base58, 32-44 chars)."""
        assert detect_chain("DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263") == "solana"

    def test_detect_chain_ethereum(self):
        """Detecta direccion EVM (0x + 40 hex chars)."""
        assert detect_chain("0x6982508145454Ce325dDbE47a25d4ec3d2311933") == "ethereum"

    def test_detect_chain_empty(self):
        """Devuelve None para string vacio."""
        assert detect_chain("") is None
        assert detect_chain(None) is None

    def test_detect_chain_invalid(self):
        """Devuelve None para formato no reconocido."""
        assert detect_chain("not_an_address") is None
        assert detect_chain("0xinvalid") is None


# ============================================================
# Tests para tokenomics features
# ============================================================

class TestTokenomicsFeatures:
    """Tests para features de tokenomics."""

    def test_basic_calculation(self):
        """Calcula features basicos con datos validos."""
        holders_df = pd.DataFrame({
            "rank": [1, 2, 3, 4, 5, 6, 7, 8, 9, 10],
            "pct_of_supply": [20.0, 15.0, 10.0, 8.0, 5.0, 4.0, 3.0, 2.0, 1.5, 1.0],
            "amount": [2e9, 1.5e9, 1e9, 8e8, 5e8, 4e8, 3e8, 2e8, 1.5e8, 1e8],
        })
        contract_info = {
            "has_mint_authority": False,
            "total_supply": 1e10,
        }

        result = compute_tokenomics_features(holders_df, contract_info)

        assert isinstance(result, dict)
        assert result["top1_holder_pct"] == 20.0
        assert result["top5_holder_pct"] == 58.0  # 20+15+10+8+5
        assert result["top10_holder_pct"] == 69.5
        assert result["has_mint_authority"] == False
        assert result["total_supply_log"] is not None

    def test_empty_holders(self):
        """Maneja DataFrame de holders vacio."""
        holders_df = pd.DataFrame(columns=["rank", "pct_of_supply", "amount"])
        contract_info = {}

        result = compute_tokenomics_features(holders_df, contract_info)

        assert isinstance(result, dict)
        # Deberia devolver valores por defecto, no crashear
        assert "top1_holder_pct" in result


# ============================================================
# Tests para liquidity features
# ============================================================

class TestLiquidityFeatures:
    """Tests para features de liquidez."""

    def test_basic_calculation(self):
        """Calcula features con datos de snapshots validos."""
        snapshots_df = pd.DataFrame({
            "snapshot_time": pd.date_range("2024-01-01", periods=8, freq="D"),
            "liquidity_usd": [10000, 12000, 15000, 14000, 16000, 18000, 17000, 20000],
            "volume_24h": [5000, 8000, 12000, 7000, 9000, 11000, 6000, 10000],
            "market_cap": [50000, 60000, 80000, 70000, 90000, 100000, 85000, 110000],
        })

        result = compute_liquidity_features(snapshots_df)

        assert isinstance(result, dict)
        assert result["initial_liquidity_usd"] == 10000
        assert "liquidity_growth_7d" in result
        assert "liq_to_mcap_ratio" in result

    def test_empty_snapshots(self):
        """Maneja DataFrame vacio."""
        snapshots_df = pd.DataFrame(
            columns=["snapshot_time", "liquidity_usd", "volume_24h", "market_cap"]
        )

        result = compute_liquidity_features(snapshots_df)
        assert isinstance(result, dict)


# ============================================================
# Tests para price action features
# ============================================================

class TestPriceActionFeatures:
    """Tests para features de price action."""

    def test_basic_calculation(self):
        """Calcula features con datos OHLCV validos."""
        # 10 dias de datos simulados
        np.random.seed(42)
        n_candles = 10
        base_price = 1.0
        prices = base_price * np.cumprod(1 + np.random.normal(0.02, 0.1, n_candles))

        ohlcv_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=n_candles, freq="D"),
            "open": prices * 0.98,
            "high": prices * 1.05,
            "low": prices * 0.95,
            "close": prices,
            "volume": np.random.uniform(1000, 10000, n_candles),
        })

        result = compute_price_action_features(ohlcv_df)

        assert isinstance(result, dict)
        assert "return_7d" not in result  # return_7d eliminado (target leakage)
        assert "volatility_7d" in result
        assert "green_candle_ratio_24h" in result

    def test_single_candle(self):
        """Maneja un solo datapoint."""
        ohlcv_df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2024-01-01")],
            "open": [1.0],
            "high": [1.1],
            "low": [0.9],
            "close": [1.05],
            "volume": [5000],
        })

        result = compute_price_action_features(ohlcv_df)
        assert isinstance(result, dict)


# ============================================================
# Tests para social features
# ============================================================

class TestSocialFeatures:
    """Tests para features sociales (buyer/seller)."""

    def test_basic_calculation(self):
        """Calcula features con datos de DexScreener."""
        snapshot = {
            "buyers_24h": 150,
            "sellers_24h": 100,
            "makers_24h": 50,
            "tx_count_24h": 500,
            "volume_24h": 100000,
            "is_boosted": True,
        }

        result = compute_social_features(snapshot)

        assert isinstance(result, dict)
        assert result["buyers_24h"] == 150
        assert result["sellers_24h"] == 100
        assert result["buyer_seller_ratio_24h"] == 1.5
        assert result["avg_tx_size_usd"] == 200.0
        assert result["is_boosted"] == True

    def test_zero_sellers(self):
        """Maneja 0 sellers sin division por cero."""
        snapshot = {
            "buyers_24h": 100,
            "sellers_24h": 0,
            "makers_24h": 10,
            "tx_count_24h": 0,
            "volume_24h": 0,
            "is_boosted": False,
        }

        result = compute_social_features(snapshot)
        assert isinstance(result, dict)
        # No deberia crashear por division por cero


# ============================================================
# Tests para temporal social features
# ============================================================

class TestTemporalSocialFeatures:
    """Tests para features sociales temporales."""

    def test_basic_calculation(self):
        """Calcula features con multiples snapshots."""
        snapshots_df = pd.DataFrame({
            "snapshot_time": pd.date_range("2024-01-01", periods=5, freq="D"),
            "buyers_24h": [100, 120, 150, 180, 200],
            "sellers_24h": [80, 90, 100, 110, 100],
            "volume_24h": [50000, 60000, 55000, 70000, 65000],
            "tx_count_24h": [200, 250, 300, 320, 350],
        })

        result = compute_temporal_social_features(snapshots_df)

        assert isinstance(result, dict)
        assert result["buyer_growth_rate"] is not None
        assert result["buyer_growth_rate"] > 0  # Compradores crecieron
        assert result["volume_consistency"] is not None
        assert result["volume_consistency"] > 0

    def test_empty_snapshots(self):
        """Maneja DataFrame vacio."""
        result = compute_temporal_social_features(pd.DataFrame())
        assert isinstance(result, dict)
        assert result["buyer_growth_rate"] is None

    def test_single_snapshot(self):
        """Maneja un solo snapshot (necesita 2+ para tendencia)."""
        snapshots_df = pd.DataFrame({
            "snapshot_time": [pd.Timestamp("2024-01-01")],
            "buyers_24h": [100],
            "sellers_24h": [80],
            "volume_24h": [50000],
            "tx_count_24h": [200],
        })
        result = compute_temporal_social_features(snapshots_df)
        assert isinstance(result, dict)
        assert result["buyer_growth_rate"] is None


# ============================================================
# Tests para contract features
# ============================================================

class TestContractFeatures:
    """Tests para features de contrato."""

    def test_basic_calculation(self):
        """Calcula features con datos validos."""
        contract_info = {
            "is_verified": True,
            "is_renounced": True,
        }

        result = compute_contract_features(
            contract_info=contract_info,
            created_at="2024-01-01T00:00:00Z",
            first_trade_at="2024-01-01T02:00:00Z",
        )

        assert isinstance(result, dict)
        assert result["is_verified"] == True
        assert result["is_renounced"] == True
        assert result["contract_age_hours"] == pytest.approx(2.0, abs=0.1)

    def test_missing_data(self):
        """Maneja datos faltantes."""
        result = compute_contract_features(
            contract_info={},
            created_at=None,
            first_trade_at=None,
        )
        assert isinstance(result, dict)


# ============================================================
# Tests para volatility advanced features
# ============================================================

class TestVolatilityAdvancedFeatures:
    """Tests para features avanzados de volatilidad."""

    def test_basic_calculation(self):
        """Calcula features con datos OHLCV validos."""
        # Crear datos OHLCV simulados (10 candles con volatilidad)
        timestamps = pd.date_range(
            start="2024-01-01 00:00:00",
            periods=10,
            freq="1h",
            tz="UTC"
        )

        ohlcv_df = pd.DataFrame({
            "timestamp": timestamps,
            "open": [1.0, 1.1, 1.2, 1.15, 1.25, 1.3, 1.2, 1.35, 1.4, 1.3],
            "high": [1.15, 1.25, 1.3, 1.25, 1.35, 1.4, 1.3, 1.45, 1.5, 1.4],
            "low": [0.95, 1.05, 1.15, 1.1, 1.2, 1.25, 1.15, 1.3, 1.35, 1.25],
            "close": [1.1, 1.2, 1.15, 1.25, 1.3, 1.2, 1.35, 1.4, 1.3, 1.35],
            "volume": [1000, 1200, 1100, 1300, 1500, 1400, 1600, 1800, 1700, 1900],
        })

        result = compute_volatility_advanced_features(ohlcv_df)

        # Verificar estructura basica
        assert isinstance(result, dict)

        # Verificar que se calcularon los features de Bollinger Bands
        assert "bb_upper_7d" in result
        assert "bb_lower_7d" in result
        assert "bb_pct_b_7d" in result
        assert "bb_bandwidth_7d" in result

        # Verificar que se calcularon los features de ATR
        assert "atr_7d" in result
        assert "atr_pct_7d" in result

        # Verificar que se calcularon los features de RSI
        assert "rsi_7d" in result
        assert "rsi_divergence_7d" in result

        # Verificar que se calcularon los features de rango intraday
        assert "avg_intraday_range_7d" in result
        assert "max_intraday_range_7d" in result

        # Verificar que se calcularon los features de volatility spikes
        assert "volatility_spike_count_7d" in result

        # Verificar que los valores calculados tienen sentido
        # (no son None y estan en rangos razonables)
        if result["bb_upper_7d"] is not None:
            assert result["bb_upper_7d"] > result["bb_lower_7d"]

        if result["bb_pct_b_7d"] is not None:
            # %B puede estar fuera de [0, 1] en casos extremos, pero no deberia ser negativo
            assert result["bb_pct_b_7d"] >= -1.0

        if result["rsi_7d"] is not None:
            # RSI debe estar entre 0 y 100
            assert 0 <= result["rsi_7d"] <= 100

        if result["atr_7d"] is not None:
            # ATR debe ser positivo
            assert result["atr_7d"] > 0

    def test_empty_dataframe(self):
        """Maneja DataFrame OHLCV vacio."""
        ohlcv_df = pd.DataFrame(
            columns=["timestamp", "open", "high", "low", "close", "volume"]
        )

        result = compute_volatility_advanced_features(ohlcv_df)

        # Debe devolver dict con todos los features = None
        assert isinstance(result, dict)
        assert result["bb_upper_7d"] is None
        assert result["atr_7d"] is None
        assert result["rsi_7d"] is None

    def test_insufficient_data(self):
        """Maneja caso con solo 1 candle."""
        ohlcv_df = pd.DataFrame({
            "timestamp": [pd.Timestamp("2024-01-01 00:00:00", tz="UTC")],
            "open": [1.0],
            "high": [1.2],
            "low": [0.9],
            "close": [1.1],
            "volume": [1000],
        })

        result = compute_volatility_advanced_features(ohlcv_df)

        # Debe devolver dict sin crashear
        assert isinstance(result, dict)

        # La mayoria de features deberian ser None (no hay suficientes datos)
        # pero no debe lanzar excepciones

    def test_extreme_volatility(self):
        """Maneja caso de volatilidad extrema (pump and dump)."""
        timestamps = pd.date_range(
            start="2024-01-01 00:00:00",
            periods=5,
            freq="1h",
            tz="UTC"
        )

        # Simular pump rapido seguido de dump
        ohlcv_df = pd.DataFrame({
            "timestamp": timestamps,
            "open": [1.0, 2.0, 5.0, 3.0, 1.5],
            "high": [2.0, 5.0, 8.0, 4.0, 2.0],
            "low": [0.8, 1.8, 4.5, 1.5, 1.0],
            "close": [2.0, 5.0, 3.0, 1.5, 1.2],
            "volume": [10000, 50000, 100000, 80000, 40000],
        })

        result = compute_volatility_advanced_features(ohlcv_df)

        # Debe calcular features sin crashear
        assert isinstance(result, dict)

        # En este caso de volatilidad extrema:
        # - ATR deberia ser alto
        # - Deberia haber volatility spikes
        # - Rango intraday deberia ser alto
        if result["atr_7d"] is not None:
            assert result["atr_7d"] > 0

        if result["volatility_spike_count_7d"] is not None:
            assert result["volatility_spike_count_7d"] >= 0

    def test_zero_prices(self):
        """Maneja caso con precios en cero (datos corruptos)."""
        ohlcv_df = pd.DataFrame({
            "timestamp": pd.date_range("2024-01-01", periods=5, freq="1h", tz="UTC"),
            "open": [0, 0, 0, 0, 0],
            "high": [0, 0, 0, 0, 0],
            "low": [0, 0, 0, 0, 0],
            "close": [0, 0, 0, 0, 0],
            "volume": [0, 0, 0, 0, 0],
        })

        result = compute_volatility_advanced_features(ohlcv_df)

        # Debe manejar el caso sin crashear
        assert isinstance(result, dict)

        # Todos los features deberian ser None o 0
        # (no puede calcular features con precios = 0)


# ============================================================
# Tests para whale movement features
# ============================================================

class TestWhaleMovementFeatures:
    """Tests para features de movimiento de ballenas."""

    def test_basic_calculation(self):
        """Calcula features con 2 snapshots de holders."""
        all_holders_df = pd.DataFrame({
            "snapshot_time": (
                ["2024-01-01"] * 5 + ["2024-01-08"] * 5
            ),
            "rank": [1, 2, 3, 4, 5] * 2,
            "holder_address": [
                "whale1", "whale2", "whale3", "whale4", "whale5",
                "whale1", "new_whale", "whale3", "whale4", "whale6",
            ],
            "pct_of_supply": [
                20.0, 15.0, 10.0, 8.0, 5.0,
                25.0, 12.0, 10.0, 7.0, 6.0,
            ],
        })

        result = compute_whale_movement_features(all_holders_df)

        assert isinstance(result, dict)
        assert result["whale_accumulation_7d"] == 5.0  # 25 - 20
        assert result["new_whale_count"] >= 1  # new_whale y whale6 son nuevos
        assert result["whale_turnover_rate"] is not None

    def test_empty_holders(self):
        """Maneja DataFrame vacio."""
        result = compute_whale_movement_features(pd.DataFrame())
        assert isinstance(result, dict)
        assert result["whale_accumulation_7d"] is None

    def test_single_snapshot(self):
        """Maneja un solo snapshot (necesita 2+)."""
        df = pd.DataFrame({
            "snapshot_time": ["2024-01-01"] * 3,
            "rank": [1, 2, 3],
            "holder_address": ["a", "b", "c"],
            "pct_of_supply": [30.0, 20.0, 10.0],
        })
        result = compute_whale_movement_features(df)
        assert isinstance(result, dict)
        assert result["whale_accumulation_7d"] is None


# ============================================================
# Tests para contract risk features
# ============================================================

class TestContractRiskFeatures:
    """Tests para features de riesgo del contrato."""

    def test_risky_contract(self):
        """Detecta funciones peligrosas en un contrato."""
        contract_source = {
            "source_code": """
                function mint(address to, uint256 amount) public onlyOwner {
                    _mint(to, amount);
                }
                function pause() public onlyOwner {
                    _pause();
                }
                function blacklist(address account) public onlyOwner {
                    _blacklisted[account] = true;
                }
            """,
            "abi": "[]",
        }

        result = compute_contract_risk_features(contract_source)

        assert isinstance(result, dict)
        assert result["has_mint_function"] is True
        assert result["has_pause_function"] is True
        assert result["has_blacklist_function"] is True
        assert result["contract_risk_score"] >= 7  # Mint(3) + Pause(2) + Blacklist(2)

    def test_safe_contract(self):
        """Contrato sin funciones peligrosas = score bajo."""
        contract_source = {
            "source_code": """
                function transfer(address to, uint256 amount) public returns (bool) {
                    _transfer(msg.sender, to, amount);
                    return true;
                }
            """,
            "abi": "[]",
        }

        result = compute_contract_risk_features(contract_source)

        assert isinstance(result, dict)
        assert result["has_mint_function"] is False
        assert result["contract_risk_score"] == 0

    def test_none_source(self):
        """Maneja contrato sin source code."""
        result = compute_contract_risk_features(None)
        assert isinstance(result, dict)
        assert result["contract_risk_score"] is None


# ============================================================
# Tests para sentiment features
# ============================================================

class TestSentimentFeatures:
    """Tests para features de sentimiento social (X / Twitter)."""

    def test_basic_calculation(self):
        """Calcula features con datos de menciones validos."""
        mention_data = {
            "total_tweets": 50,
            "unique_authors": 30,
            "total_likes": 200,
            "total_retweets": 80,
            "total_replies": 40,
            "avg_engagement": 6.4,
        }

        result = compute_sentiment_features(mention_data)

        assert isinstance(result, dict)
        assert result["mention_count"] == 50
        assert result["unique_authors"] == 30
        # engagement_score = 200 + (80*3) + (40*2) = 200+240+80 = 520
        assert result["engagement_score"] == 520.0
        assert result["mention_per_author"] is not None
        assert result["mention_per_author"] > 1.0  # 50/30 ~= 1.67
        assert result["like_to_mention_ratio"] == 4.0  # 200/50
        assert result["virality_score"] is not None

    def test_empty_data(self):
        """Maneja dict vacio o None."""
        result = compute_sentiment_features(None)
        assert isinstance(result, dict)
        assert result["mention_count"] is None

        result2 = compute_sentiment_features({})
        assert isinstance(result2, dict)
        assert result2["mention_count"] is None

    def test_zero_tweets(self):
        """Maneja caso con cero tweets encontrados."""
        mention_data = {
            "total_tweets": 0,
            "unique_authors": 0,
            "total_likes": 0,
            "total_retweets": 0,
            "total_replies": 0,
            "avg_engagement": 0,
        }

        result = compute_sentiment_features(mention_data)
        assert isinstance(result, dict)
        assert result["mention_count"] is None  # 0 tweets = sin datos
