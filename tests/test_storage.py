"""
test_storage.py - Tests CRUD para Storage con SQLite temporal.

Cada test usa tmp_storage (fixture de conftest.py) que crea una DB
en un directorio temporal, sin tocar la base de datos real.
"""

import pandas as pd
import pytest


# ============================================================
# TABLAS E INICIALIZACION
# ============================================================

def test_init_creates_tables(tmp_storage):
    """Verifica que las 9 tablas se crean al inicializar."""
    tables_df = tmp_storage.query(
        "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
    )
    table_names = set(tables_df["name"].tolist())
    expected = {
        "tokens", "pool_snapshots", "ohlcv", "holder_snapshots",
        "contract_info", "labels", "features", "api_usage", "watchlist",
    }
    assert expected.issubset(table_names), f"Faltan tablas: {expected - table_names}"


# ============================================================
# TOKENS
# ============================================================

def test_upsert_token_insert(tmp_storage):
    """Inserta un token nuevo y lo recupera."""
    tmp_storage.upsert_token({
        "token_id": "tok_abc",
        "chain": "solana",
        "name": "TestCoin",
        "symbol": "TC",
    })
    df = tmp_storage.get_all_tokens()
    assert len(df) == 1
    assert df.iloc[0]["token_id"] == "tok_abc"
    assert df.iloc[0]["chain"] == "solana"
    assert df.iloc[0]["symbol"] == "TC"


def test_upsert_token_update(tmp_storage):
    """UPSERT actualiza campos con COALESCE (no sobreescribe con NULL)."""
    tmp_storage.upsert_token({
        "token_id": "tok_abc",
        "chain": "solana",
        "name": "TestCoin",
        "symbol": "TC",
        "pool_address": "pool_123",
    })
    # Segundo upsert: symbol=None no sobreescribe "TC"
    tmp_storage.upsert_token({
        "token_id": "tok_abc",
        "chain": "solana",
        "name": "TestCoinV2",
        "symbol": None,
    })
    df = tmp_storage.get_all_tokens()
    assert len(df) == 1
    assert df.iloc[0]["name"] == "TestCoinV2"
    assert df.iloc[0]["symbol"] == "TC"  # No sobreescrito
    assert df.iloc[0]["pool_address"] == "pool_123"  # Preservado


def test_get_all_tokens_by_chain(tmp_storage):
    """Filtra tokens por chain."""
    tmp_storage.upsert_token({"token_id": "sol1", "chain": "solana"})
    tmp_storage.upsert_token({"token_id": "eth1", "chain": "ethereum"})
    tmp_storage.upsert_token({"token_id": "sol2", "chain": "solana"})

    all_tokens = tmp_storage.get_all_tokens()
    assert len(all_tokens) == 3

    solana_tokens = tmp_storage.get_all_tokens(chain="solana")
    assert len(solana_tokens) == 2

    eth_tokens = tmp_storage.get_all_tokens(chain="ethereum")
    assert len(eth_tokens) == 1


# ============================================================
# OHLCV
# ============================================================

def test_insert_ohlcv_batch_and_get(tmp_storage):
    """Inserta batch de OHLCV y los lee correctamente."""
    tmp_storage.upsert_token({"token_id": "tok1", "chain": "solana"})

    rows = [
        {
            "token_id": "tok1", "chain": "solana", "pool_address": "pool1",
            "timeframe": "day", "timestamp": f"2026-02-{20+i:02d}T00:00:00Z",
            "open": 1.0 + i, "high": 1.5 + i, "low": 0.5 + i,
            "close": 1.2 + i, "volume": 1000 * (i + 1),
        }
        for i in range(5)
    ]
    tmp_storage.insert_ohlcv_batch(rows)

    df = tmp_storage.get_ohlcv("tok1", timeframe="day")
    assert len(df) == 5
    assert df.iloc[0]["open"] == 1.0
    assert df.iloc[4]["close"] == 5.2


# ============================================================
# POOL SNAPSHOTS
# ============================================================

def test_insert_pool_snapshot(tmp_storage):
    """Inserta un snapshot de pool."""
    tmp_storage.upsert_token({"token_id": "tok1", "chain": "solana"})
    tmp_storage.insert_pool_snapshot({
        "token_id": "tok1",
        "chain": "solana",
        "snapshot_time": "2026-03-01T12:00:00Z",
        "price_usd": 0.001,
        "volume_24h": 50000,
        "liquidity_usd": 25000,
    })

    df = tmp_storage.query(
        "SELECT * FROM pool_snapshots WHERE token_id = ?", ("tok1",)
    )
    assert len(df) == 1
    assert df.iloc[0]["price_usd"] == 0.001


# ============================================================
# LABELS
# ============================================================

def test_upsert_label(tmp_storage):
    """Inserta y actualiza labels."""
    tmp_storage.upsert_token({"token_id": "tok1", "chain": "solana"})

    tmp_storage.upsert_label({
        "token_id": "tok1",
        "label_multi": "failure",
        "label_binary": 0,
        "max_multiple": 0.5,
        "final_multiple": 0.1,
    })

    df = tmp_storage.query("SELECT * FROM labels WHERE token_id = ?", ("tok1",))
    assert len(df) == 1
    assert df.iloc[0]["label_binary"] == 0

    # Actualizar
    tmp_storage.upsert_label({
        "token_id": "tok1",
        "label_multi": "gem",
        "label_binary": 1,
        "max_multiple": 15.0,
        "final_multiple": 10.0,
    })

    df = tmp_storage.query("SELECT * FROM labels WHERE token_id = ?", ("tok1",))
    assert len(df) == 1
    assert df.iloc[0]["label_binary"] == 1
    assert df.iloc[0]["max_multiple"] == 15.0


# ============================================================
# FEATURES
# ============================================================

def test_save_features_df_and_get(tmp_storage):
    """Guarda y recupera features como DataFrame."""
    features_df = pd.DataFrame({
        "token_id": ["tok1", "tok2"],
        "feature_a": [1.0, 2.0],
        "feature_b": [3.0, 4.0],
    }).set_index("token_id")

    tmp_storage.save_features_df(features_df)

    recovered = tmp_storage.get_features_df()
    assert len(recovered) == 2
    assert "feature_a" in recovered.columns


# ============================================================
# WATCHLIST
# ============================================================

def test_watchlist_crud(tmp_storage):
    """CRUD completo de watchlist."""
    tmp_storage.upsert_token({"token_id": "tok1", "chain": "solana"})

    # Agregar
    tmp_storage.add_to_watchlist("tok1", "solana", "Parece prometedor")
    assert tmp_storage.is_in_watchlist("tok1") is True
    assert tmp_storage.is_in_watchlist("tok_nonexistent") is False

    # Listar
    wl = tmp_storage.get_watchlist()
    assert len(wl) >= 1

    # Eliminar
    tmp_storage.remove_from_watchlist("tok1")
    assert tmp_storage.is_in_watchlist("tok1") is False


# ============================================================
# ESTADISTICAS
# ============================================================

def test_stats(tmp_storage):
    """Conteos correctos en stats()."""
    tmp_storage.upsert_token({"token_id": "tok1", "chain": "solana"})
    tmp_storage.upsert_token({"token_id": "tok2", "chain": "ethereum"})

    stats = tmp_storage.stats()
    assert stats["tokens"] == 2
    assert stats["labels"] == 0
    assert stats["ohlcv"] == 0


# ============================================================
# TIPO DE RETORNO
# ============================================================

def test_query_returns_dataframe(tmp_storage):
    """query() siempre devuelve un pd.DataFrame."""
    result = tmp_storage.query("SELECT 1 as test")
    assert isinstance(result, pd.DataFrame)
    assert result.iloc[0]["test"] == 1
