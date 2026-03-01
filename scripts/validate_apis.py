"""
validate_apis.py - Verifica la conectividad y estado de todas las APIs.

Ejecutar: python scripts/validate_apis.py

Para cada API:
  - Intenta una llamada real
  - Reporta OK / ERROR / SKIP (si no tiene API key)
  - Muestra detalles utiles (rate limit restante, etc.)
"""

import sys
from pathlib import Path

# Agregar raiz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

import time
from config import (
    HELIUS_API_KEY,
    ETHERSCAN_API_KEY,
    BASESCAN_API_KEY,
    COINGECKO_API_KEY,
)


def check_geckoterminal():
    """Verifica GeckoTerminal (no requiere API key)."""
    print("\n[1/5] GeckoTerminal (OHLCV, pools, trending)")
    print("      Key requerida: No")
    try:
        from src.api import CoinGeckoClient
        client = CoinGeckoClient()
        # Intentar obtener pools trending de Solana
        pools = client.get_new_pools("solana", page=1)
        if pools:
            print(f"      Estado: OK - {len(pools)} pools obtenidos")
            print(f"      Ejemplo: {pools[0].get('name', 'N/A')}")
            return True
        else:
            print("      Estado: WARNING - Respuesta vacia (posible rate limit)")
            return False
    except Exception as e:
        print(f"      Estado: ERROR - {e}")
        return False


def check_dexscreener():
    """Verifica DexScreener (no requiere API key)."""
    print("\n[2/5] DexScreener (buyers/sellers, boosts, precio)")
    print("      Key requerida: No")
    try:
        from src.api import DexScreenerClient
        client = DexScreenerClient()
        # Intentar obtener datos de BONK (token conocido)
        bonk_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        pairs = client.get_token_pairs("solana", bonk_address)
        if pairs:
            pair = pairs[0] if isinstance(pairs, list) else pairs
            price = pair.get("price_usd", "N/A")
            print(f"      Estado: OK - BONK precio: ${price}")
            return True
        else:
            print("      Estado: WARNING - Sin datos para BONK")
            return False
    except Exception as e:
        print(f"      Estado: ERROR - {e}")
        return False


def check_helius():
    """Verifica Helius RPC (requiere API key para holders)."""
    print("\n[3/5] Helius / Solana RPC (holders, token supply)")
    print(f"      Key requerida: Si | Key presente: {'Si' if HELIUS_API_KEY else 'No'}")
    if not HELIUS_API_KEY:
        print("      Estado: SKIP - Sin API key. Registrate en https://www.helius.dev/")
        return None
    try:
        from src.api import SolanaRPC
        client = SolanaRPC()
        # Intentar obtener supply de BONK
        bonk_address = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
        supply = client.get_token_supply(bonk_address)
        if supply:
            print(f"      Estado: OK - BONK supply obtenido")
            # Intentar holders
            holders = client.get_token_largest_accounts(bonk_address)
            if holders:
                print(f"      Holders: OK - {len(holders)} top holders obtenidos")
            else:
                print("      Holders: WARNING - No se pudieron obtener (RPC publico?)")
            return True
        else:
            print("      Estado: WARNING - Sin respuesta de supply")
            return False
    except Exception as e:
        print(f"      Estado: ERROR - {e}")
        return False


def check_etherscan():
    """Verifica Etherscan V2 (requiere API key)."""
    print("\n[4/5] Etherscan V2 (contract verification, ETH + Base)")
    print(f"      Key requerida: Si | Key presente: {'Si' if ETHERSCAN_API_KEY else 'No'}")
    if not ETHERSCAN_API_KEY:
        print("      Estado: SKIP - Sin API key. Registrate en https://etherscan.io/myapikey")
        return None
    try:
        from src.api import EtherscanClient
        # Verificar Ethereum
        eth_client = EtherscanClient(chain="ethereum")
        # PEPE contract - sabemos que esta verificado
        pepe_address = "0x6982508145454Ce325dDbE47a25d4ec3d2311933"
        is_verified = eth_client.is_contract_verified(pepe_address)
        print(f"      Ethereum: OK - PEPE verificado: {is_verified}")

        # Verificar Base
        time.sleep(0.5)
        base_client = EtherscanClient(chain="base")
        brett_address = "0x532f27101965dd16442E59d40670FaF5eBB142E4"
        is_verified_base = base_client.is_contract_verified(brett_address)
        print(f"      Base: OK - BRETT verificado: {is_verified_base}")
        return True
    except Exception as e:
        print(f"      Estado: ERROR - {e}")
        return False


def check_coingecko():
    """Verifica CoinGecko Demo API (opcional)."""
    print("\n[5/5] CoinGecko Demo (precios BTC/ETH/SOL - OPCIONAL)")
    print(f"      Key requerida: No (opcional) | Key presente: {'Si' if COINGECKO_API_KEY else 'No'}")
    try:
        from src.api import CoinGeckoClient
        client = CoinGeckoClient()
        # Intentar obtener precio de Bitcoin
        historial = client.get_coin_price_history("bitcoin", days=1)
        if historial and historial.get("prices"):
            ultimo_precio = historial["prices"][-1][1]
            print(f"      Estado: OK - BTC precio: ${ultimo_precio:,.2f}")
            return True
        else:
            print("      Estado: WARNING - Sin datos de precio")
            return False
    except Exception as e:
        print(f"      Estado: ERROR - {e}")
        return False


def main():
    """Ejecuta todas las verificaciones."""
    print("=" * 60)
    print("VALIDACION DE APIs - Memecoin Gem Detector")
    print("=" * 60)

    resultados = {}

    # Ejecutar cada verificacion con pausa entre ellas
    resultados["GeckoTerminal"] = check_geckoterminal()
    time.sleep(1)
    resultados["DexScreener"] = check_dexscreener()
    time.sleep(1)
    resultados["Helius"] = check_helius()
    time.sleep(1)
    resultados["Etherscan"] = check_etherscan()
    time.sleep(1)
    resultados["CoinGecko"] = check_coingecko()

    # Resumen
    print("\n" + "=" * 60)
    print("RESUMEN")
    print("=" * 60)

    ok_count = 0
    skip_count = 0
    error_count = 0

    for api, estado in resultados.items():
        if estado is True:
            icono = "OK"
            ok_count += 1
        elif estado is None:
            icono = "SKIP"
            skip_count += 1
        else:
            icono = "ERROR"
            error_count += 1
        print(f"  {api:20s} -> {icono}")

    print(f"\nTotal: {ok_count} OK, {skip_count} SKIP, {error_count} ERROR")

    if skip_count > 0:
        print("\nPara las APIs con SKIP, necesitas configurar las API keys:")
        print("  1. Copia: cp .env.example .env")
        print("  2. Edita .env con tus keys")
        print("  3. Re-ejecuta: python scripts/validate_apis.py")

    if error_count > 0:
        print("\nLas APIs con ERROR pueden tener problemas de red o rate limiting.")
        print("Intenta de nuevo en unos minutos.")

    return error_count == 0


if __name__ == "__main__":
    exito = main()
    sys.exit(0 if exito else 1)
