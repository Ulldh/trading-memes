#!/usr/bin/env python3
"""
enrich_security.py - Enriquece tokens existentes con datos de seguridad.

Llama a GoPlus API (gratis, batch de 100) y RugCheck (Solana only)
para obtener datos de seguridad: honeypot, taxes, ownership risks.

Los datos se guardan en la tabla security_data de Supabase.
Los features se recalculan automaticamente en el proximo retrain.

Uso:
    python scripts/enrich_security.py --max-tokens 500
    python scripts/enrich_security.py --chain solana --max-tokens 200
    python scripts/enrich_security.py --source goplus  # solo GoPlus
    python scripts/enrich_security.py --source rugcheck  # solo RugCheck (Solana)
"""

import argparse
import json
import sys
import time
from pathlib import Path

# Agregar directorio raiz al path para imports
project_root = Path(__file__).parent.parent.resolve()
sys.path.insert(0, str(project_root))

from src.api.goplus_client import GoPlusClient, GOPLUS_CHAIN_IDS
from src.api.rugcheck_client import RugCheckClient
from src.data.supabase_storage import get_storage
from src.utils.logger import get_logger

logger = get_logger(__name__)


def get_tokens_without_security(storage, chain=None, max_tokens=500, source="all"):
    """
    Obtiene tokens que NO tienen datos de seguridad todavia.

    Hace un LEFT JOIN entre tokens y security_data para encontrar
    los que faltan. Opcionalmente filtra por cadena.

    Args:
        storage: Instancia de SupabaseStorage.
        chain: Filtrar por cadena ("solana", "ethereum", "base"). None = todas.
        max_tokens: Maximo de tokens a devolver.
        source: "goplus", "rugcheck", o "all".

    Returns:
        Lista de dicts con token_id y chain.
    """
    # Construir la consulta segun la fuente
    # Para GoPlus: tokens sin goplus_data en security_data
    # Para RugCheck: tokens Solana sin rugcheck_data en security_data
    # Para "all": tokens sin ningun dato de seguridad
    if source == "rugcheck":
        # RugCheck solo soporta Solana
        sql = (
            "SELECT t.token_id, t.chain FROM tokens t "
            "LEFT JOIN security_data sd ON t.token_id = sd.token_id "
            "WHERE (sd.token_id IS NULL OR sd.rugcheck_data IS NULL) "
            "AND t.chain = 'solana' "
            f"LIMIT {int(max_tokens)}"
        )
    elif source == "goplus":
        sql = (
            "SELECT t.token_id, t.chain FROM tokens t "
            "LEFT JOIN security_data sd ON t.token_id = sd.token_id "
            "WHERE (sd.token_id IS NULL OR sd.goplus_data IS NULL)"
        )
        if chain:
            sql += f" AND t.chain = '{chain}'"
        sql += f" LIMIT {int(max_tokens)}"
    else:
        # "all": tokens sin ningun dato de seguridad
        sql = (
            "SELECT t.token_id, t.chain FROM tokens t "
            "LEFT JOIN security_data sd ON t.token_id = sd.token_id "
            "WHERE sd.token_id IS NULL"
        )
        if chain:
            sql += f" AND t.chain = '{chain}'"
        sql += f" LIMIT {int(max_tokens)}"

    df = storage.query(sql)

    if df.empty:
        return []

    return df.to_dict("records")


def enrich_goplus(storage, tokens, batch_size=100):
    """
    Enriquece tokens con datos de GoPlus (batch de 100 por cadena).

    GoPlus soporta multiples direcciones en una sola llamada,
    agrupadas por cadena. Mucho mas eficiente que llamar de a uno.

    Args:
        storage: Instancia de SupabaseStorage.
        tokens: Lista de dicts con token_id y chain.
        batch_size: Tamano del batch por llamada (max 100 para GoPlus).

    Returns:
        Tuple (exitos, fallos) con conteo de resultados.
    """
    client = GoPlusClient()
    exitos = 0
    fallos = 0

    # Agrupar tokens por cadena (GoPlus requiere batch por cadena)
    tokens_by_chain = {}
    for token in tokens:
        chain = token["chain"]
        if chain not in GOPLUS_CHAIN_IDS:
            logger.debug(f"GoPlus: cadena '{chain}' no soportada, saltando {token['token_id'][:12]}...")
            fallos += 1
            continue
        tokens_by_chain.setdefault(chain, []).append(token["token_id"])

    total_tokens = sum(len(v) for v in tokens_by_chain.values())
    logger.info(f"GoPlus: {total_tokens} tokens en {len(tokens_by_chain)} cadenas")

    processed = 0
    for chain, addresses in tokens_by_chain.items():
        logger.info(f"  Procesando {chain}: {len(addresses)} tokens")

        # Procesar en batches de 100 (limite de GoPlus)
        for i in range(0, len(addresses), batch_size):
            batch = addresses[i:i + batch_size]

            try:
                # GoPlus soporta batch de hasta 100 direcciones por llamada
                results = client.get_tokens_security(chain, batch)

                # Guardar cada resultado en security_data
                for addr in batch:
                    addr_lower = addr.lower()
                    data = results.get(addr_lower, results.get(addr, {}))

                    if data:
                        storage.upsert_security_data({
                            "token_id": addr,
                            "chain": chain,
                            "goplus_data": json.dumps(data),
                        })
                        exitos += 1
                    else:
                        # GoPlus no tiene datos para este token (normal para tokens nuevos)
                        fallos += 1

                processed += len(batch)
                if processed % 200 == 0 or processed == total_tokens:
                    logger.info(
                        f"  Progreso: {processed}/{total_tokens} "
                        f"({exitos} exitos, {fallos} sin datos)"
                    )

            except Exception as e:
                logger.warning(
                    f"  Error en batch GoPlus ({chain}, "
                    f"{len(batch)} tokens): {e}"
                )
                fallos += len(batch)
                processed += len(batch)

    return exitos, fallos


def enrich_rugcheck(storage, tokens):
    """
    Enriquece tokens Solana con datos de RugCheck (1 por llamada).

    RugCheck solo soporta Solana y no tiene batch API,
    asi que se llama de a uno con rate limiting (1 req/s).

    Args:
        storage: Instancia de SupabaseStorage.
        tokens: Lista de dicts con token_id y chain.

    Returns:
        Tuple (exitos, fallos) con conteo de resultados.
    """
    client = RugCheckClient()
    exitos = 0
    fallos = 0

    # Filtrar solo tokens de Solana (RugCheck no soporta otras cadenas)
    solana_tokens = [t for t in tokens if t["chain"] == "solana"]
    total = len(solana_tokens)

    if total == 0:
        logger.info("RugCheck: no hay tokens de Solana para enriquecer")
        return 0, 0

    logger.info(f"RugCheck: {total} tokens de Solana")

    for i, token in enumerate(solana_tokens):
        token_id = token["token_id"]

        try:
            report = client.get_report(token_id)

            if report:
                storage.upsert_security_data({
                    "token_id": token_id,
                    "chain": "solana",
                    "rugcheck_data": json.dumps(report),
                })
                exitos += 1
            else:
                fallos += 1

        except Exception as e:
            logger.warning(
                f"  Error RugCheck para {token_id[:12]}...: {e}"
            )
            fallos += 1

        # Mostrar progreso cada 50 tokens
        if (i + 1) % 50 == 0 or (i + 1) == total:
            logger.info(
                f"  Progreso: {i+1}/{total} "
                f"({exitos} exitos, {fallos} sin datos)"
            )

    return exitos, fallos


def main():
    """
    Punto de entrada principal del script de enriquecimiento.

    Lee argumentos de CLI, conecta a la DB, busca tokens sin datos
    de seguridad y los enriquece con GoPlus y/o RugCheck.
    """
    parser = argparse.ArgumentParser(
        description="Enriquece tokens con datos de seguridad (GoPlus + RugCheck)"
    )
    parser.add_argument(
        "--max-tokens", type=int, default=500,
        help="Maximo de tokens a procesar (default 500)"
    )
    parser.add_argument(
        "--chain", type=str, default=None,
        choices=["solana", "ethereum", "base"],
        help="Filtrar por cadena (default: todas)"
    )
    parser.add_argument(
        "--source", type=str, default="all",
        choices=["all", "goplus", "rugcheck"],
        help="Fuente de datos: goplus, rugcheck, o all (default: all)"
    )
    args = parser.parse_args()

    logger.info("=" * 60)
    logger.info("ENRIQUECIMIENTO DE SEGURIDAD")
    logger.info(f"  max_tokens={args.max_tokens}, chain={args.chain or 'todas'}, source={args.source}")
    logger.info("=" * 60)

    # Conectar a la DB
    storage = get_storage()

    # Obtener tokens sin datos de seguridad
    tokens = get_tokens_without_security(
        storage,
        chain=args.chain,
        max_tokens=args.max_tokens,
        source=args.source,
    )

    if not tokens:
        logger.info("No hay tokens pendientes de enriquecimiento de seguridad")
        print("No hay tokens pendientes de enriquecimiento.")
        return

    logger.info(f"Encontrados {len(tokens)} tokens sin datos de seguridad")

    # Contadores globales
    total_exitos = 0
    total_fallos = 0

    t0 = time.time()

    # --- GoPlus (batch de 100, todas las cadenas) ---
    if args.source in ("all", "goplus"):
        logger.info("\n--- GoPlus Security API ---")
        exitos, fallos = enrich_goplus(storage, tokens)
        total_exitos += exitos
        total_fallos += fallos
        logger.info(f"GoPlus completado: {exitos} exitos, {fallos} sin datos")

    # --- RugCheck (secuencial, solo Solana) ---
    if args.source in ("all", "rugcheck"):
        logger.info("\n--- RugCheck API (Solana) ---")
        exitos, fallos = enrich_rugcheck(storage, tokens)
        total_exitos += exitos
        total_fallos += fallos
        logger.info(f"RugCheck completado: {exitos} exitos, {fallos} sin datos")

    elapsed = time.time() - t0

    # Resumen final
    logger.info("=" * 60)
    logger.info("RESUMEN DE ENRIQUECIMIENTO")
    logger.info(f"  Tokens procesados: {len(tokens)}")
    logger.info(f"  Exitos: {total_exitos}")
    logger.info(f"  Sin datos: {total_fallos}")
    logger.info(f"  Tiempo: {elapsed:.1f}s")
    logger.info("=" * 60)

    print(
        f"\nEnriquecimiento completado: {total_exitos} exitos, "
        f"{total_fallos} sin datos ({elapsed:.1f}s)"
    )


if __name__ == "__main__":
    main()
