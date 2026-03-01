"""
expand_seed.py - Procesa los seed tokens expandidos.

Para cada token en data/seed_tokens.py:
  1. Lo registra en la base de datos (upsert_token)
  2. Recopila datos via collector.collect_single_token()
  3. Calcula features via FeatureBuilder.build_features_for_token()
  4. Asigna labels conocidos (basados en la categoria del seed)
  5. Re-entrena modelos RF + XGBoost

Uso:
    python scripts/expand_seed.py              # Procesa todos
    python scripts/expand_seed.py --skip-existing  # Solo tokens nuevos
    python scripts/expand_seed.py --dry-run    # Solo muestra lo que haria
"""

import sys
import time
import json
import argparse
from pathlib import Path

# Agregar raiz del proyecto al path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.data.storage import Storage
from src.data.collector import DataCollector
from src.features.builder import FeatureBuilder
from src.models.labeler import Labeler
from src.utils.logger import get_logger
from data.seed_tokens import get_all_seed_tokens

logger = get_logger(__name__)


def parse_args():
    parser = argparse.ArgumentParser(description="Procesa seed tokens expandidos")
    parser.add_argument(
        "--skip-existing", action="store_true",
        help="Saltar tokens que ya estan en la DB"
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Solo mostrar lo que se haria, sin ejecutar"
    )
    parser.add_argument(
        "--skip-retrain", action="store_true",
        help="No re-entrenar modelos al final"
    )
    parser.add_argument(
        "--category", type=str, default=None,
        help="Solo procesar una categoria (gem, moderate_success, failure, rug)"
    )
    return parser.parse_args()


def main():
    args = parse_args()

    print("=" * 60)
    print("EXPANSION DEL SEED DATASET")
    print("=" * 60)

    # Obtener todos los seed tokens
    all_tokens = get_all_seed_tokens()

    # Filtrar por categoria si se especifica
    if args.category:
        all_tokens = [t for t in all_tokens if t["category"] == args.category]
        print(f"Filtrado a categoria '{args.category}': {len(all_tokens)} tokens")

    # Resumen
    categories = {}
    for t in all_tokens:
        cat = t["category"]
        categories[cat] = categories.get(cat, 0) + 1

    print(f"\nTotal: {len(all_tokens)} tokens")
    for cat, count in sorted(categories.items()):
        print(f"  {cat}: {count}")

    if args.dry_run:
        print("\n[DRY RUN] No se ejecutara nada. Tokens a procesar:")
        for t in all_tokens:
            print(f"  {t['symbol']:10s} ({t['chain']:10s}) [{t['category']}]")
        return

    # Inicializar componentes
    storage = Storage()
    collector = DataCollector(storage)
    builder = FeatureBuilder(storage)
    labeler = Labeler(storage)

    # Stats antes
    print("\n--- ESTADISTICAS ANTES ---")
    stats_antes = storage.stats()
    for k, v in stats_antes.items():
        print(f"  {k}: {v}")

    # Tokens existentes (para --skip-existing)
    existing_tokens = set()
    if args.skip_existing:
        df_existing = storage.get_all_tokens()
        if not df_existing.empty:
            existing_tokens = set(df_existing["token_id"].tolist())
            print(f"\nTokens existentes en DB: {len(existing_tokens)}")

    # ============================================================
    # PASO 1: Registrar tokens y recopilar datos
    # ============================================================
    print("\n--- PASO 1: Registrando tokens y recopilando datos ---")

    exitos = 0
    errores = 0
    saltados = 0

    for i, token in enumerate(all_tokens, 1):
        address = token["address"]
        chain = token["chain"]
        symbol = token["symbol"]
        category = token["category"]

        # Saltar si ya existe
        if args.skip_existing and address in existing_tokens:
            print(f"  [{i}/{len(all_tokens)}] {symbol:10s} SALTADO (ya existe)")
            saltados += 1
            continue

        print(f"  [{i}/{len(all_tokens)}] {symbol:10s} ({chain}) [{category}]...", end=" ")

        try:
            # Registrar token basico
            storage.upsert_token({
                "token_id": address,
                "chain": chain,
                "symbol": symbol,
                "name": symbol,
            })

            # Recopilar datos completos (GeckoTerminal + DexScreener + OHLCV + holders + contract)
            result = collector.collect_single_token(address, chain)

            # Verificar que se obtuvieron datos
            has_ohlcv = bool(result.get("ohlcv"))
            has_snapshot = bool(result.get("pool_snapshot"))

            if has_ohlcv:
                print(f"OK ({len(result['ohlcv'])} velas OHLCV)")
                exitos += 1
            elif has_snapshot:
                print("OK (sin OHLCV, solo snapshot)")
                exitos += 1
            else:
                print("PARCIAL (registrado pero sin datos de APIs)")
                exitos += 1

            # Pausa entre tokens para respetar rate limits
            time.sleep(2.0)

        except Exception as e:
            print(f"ERROR: {e}")
            errores += 1
            time.sleep(1.0)

    print(f"\nRecopilacion: {exitos} OK, {errores} errores, {saltados} saltados")

    # ============================================================
    # PASO 2: Asignar labels conocidos
    # ============================================================
    print("\n--- PASO 2: Asignando labels conocidos ---")

    # Mapeo de categoria a label
    CATEGORY_TO_LABEL = {
        "gem": {"label_multi": "gem", "label_binary": 1},
        "moderate_success": {"label_multi": "moderate_success", "label_binary": 1},
        "failure": {"label_multi": "failure", "label_binary": 0},
        "rug": {"label_multi": "rug", "label_binary": 0},
    }

    labels_asignados = 0
    for token in all_tokens:
        address = token["address"]
        category = token["category"]
        notes = token.get("notes", "")

        label_info = CATEGORY_TO_LABEL.get(category)
        if not label_info:
            continue

        try:
            # Para seed tokens SIEMPRE usamos la categoria conocida.
            # El auto-labeler usa OHLCV reciente que no refleja el historico real
            # (un gem como BONK hizo 100x en 2023 pero su OHLCV reciente puede mostrar caida).
            storage.upsert_label({
                "token_id": address,
                "label_multi": label_info["label_multi"],
                "label_binary": label_info["label_binary"],
                "max_multiple": None,
                "final_multiple": None,
                "notes": f"Seed dataset ({category}): {notes}",
            })

            labels_asignados += 1

        except Exception as e:
            logger.warning(f"Error asignando label a {address[:10]}: {e}")

    print(f"Labels asignados: {labels_asignados}")

    # ============================================================
    # PASO 3: Calcular features
    # ============================================================
    print("\n--- PASO 3: Calculando features ---")

    features_df = builder.build_all_features()
    print(f"Features calculados: {features_df.shape[0]} tokens x {features_df.shape[1]} features")

    # Guardar features
    storage.save_features_df(features_df)
    features_df.to_parquet("data/processed/features.parquet")
    print("Features guardados en DB y parquet")

    # ============================================================
    # PASO 4: Re-entrenar modelos (opcional)
    # ============================================================
    if not args.skip_retrain:
        print("\n--- PASO 4: Re-entrenando modelos ---")

        try:
            from src.models.trainer import ModelTrainer

            labels_df = storage.query("SELECT * FROM labels")

            if not labels_df.empty and len(labels_df) >= 10:
                trainer = ModelTrainer()
                results = trainer.train_all(features_df, labels_df, target="label_binary")

                # Guardar modelos
                trainer.save_models()

                # Guardar resultados de evaluacion
                eval_results = {}
                for name, metrics in results.items():
                    if isinstance(metrics, dict):
                        eval_results[name] = {
                            k: v for k, v in metrics.items()
                            if isinstance(v, (int, float, str, list, dict, type(None)))
                        }

                eval_path = Path("data/models/evaluation_results.json")
                with open(eval_path, "w") as f:
                    json.dump(eval_results, f, indent=2, default=str)

                # Guardar feature columns
                fc_path = Path("data/models/feature_columns.json")
                with open(fc_path, "w") as f:
                    json.dump(trainer.feature_names, f)

                # Guardar X_train y y_train
                if hasattr(trainer, "_X_train"):
                    trainer._X_train.to_csv("data/processed/X_train.csv", index=False)
                    trainer._y_train.to_csv("data/processed/y_train.csv", index=False)

                print("Modelos re-entrenados y guardados")

                # Mostrar resultados clave
                for name, metrics in results.items():
                    if isinstance(metrics, dict) and "val_f1" in metrics:
                        print(f"  {name}: F1={metrics['val_f1']:.4f}")
            else:
                print(f"Solo {len(labels_df)} labels, minimo 10 para entrenar. Saltando.")

        except Exception as e:
            print(f"Error re-entrenando: {e}")
            print("Puedes re-entrenar manualmente con: ./scripts/retrain.sh")
    else:
        print("\n[SKIP] Re-entrenamiento saltado (--skip-retrain)")

    # ============================================================
    # RESUMEN FINAL
    # ============================================================
    print("\n--- ESTADISTICAS DESPUES ---")
    stats_despues = storage.stats()
    print(f"{'Tabla':<20s} {'Antes':>8s} -> {'Despues':>8s} {'Cambio':>8s}")
    print("-" * 50)
    for k, v_despues in stats_despues.items():
        v_antes = stats_antes.get(k, 0)
        cambio = v_despues - v_antes
        signo = "+" if cambio > 0 else ""
        print(f"  {k:<18s} {v_antes:>6d} -> {v_despues:>6d}   {signo}{cambio}")

    print("\n" + "=" * 60)
    print("EXPANSION COMPLETADA")
    print("=" * 60)


if __name__ == "__main__":
    main()
