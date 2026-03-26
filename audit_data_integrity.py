"""
audit_data_integrity.py - Auditoria completa de integridad de datos.

Ejecuta verificaciones sistematicas sobre la base de datos SQLite
para detectar inconsistencias, valores invalidos, y problemas de calidad.
"""

import sys
import pandas as pd
import numpy as np
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Agregar src al path
sys.path.insert(0, str(Path(__file__).parent))

from src.data.supabase_storage import get_storage
from src.utils.logger import get_logger

logger = get_logger(__name__)

class DataIntegrityAuditor:
    """Ejecuta auditorias de integridad sobre la base de datos."""

    def __init__(self):
        self.storage = get_storage()
        self.issues = []

    def add_issue(self, severity, category, description, count=None, sql_fix=None):
        """Registra un problema encontrado."""
        self.issues.append({
            "severity": severity,  # CRITICAL, HIGH, MEDIUM, LOW, INFO
            "category": category,
            "description": description,
            "count": count,
            "sql_fix": sql_fix
        })

    def run_all_checks(self):
        """Ejecuta todas las verificaciones de integridad."""
        print("\n" + "="*80)
        print("AUDITORIA DE INTEGRIDAD DE DATOS - Trading Memes")
        print("="*80 + "\n")

        # Estadisticas generales
        print("1. ESTADISTICAS GENERALES")
        print("-" * 80)
        self.check_general_stats()

        # Verificaciones de integridad
        print("\n2. VERIFICACION DE CHAINS")
        print("-" * 80)
        self.check_chains()

        print("\n3. VERIFICACION DE OHLCV")
        print("-" * 80)
        self.check_ohlcv_integrity()

        print("\n4. VERIFICACION DE LABELS")
        print("-" * 80)
        self.check_labels_integrity()

        print("\n5. VERIFICACION DE FEATURES")
        print("-" * 80)
        self.check_features_integrity()

        print("\n6. VERIFICACION DE REGISTROS HUERFANOS")
        print("-" * 80)
        self.check_orphaned_records()

        print("\n7. VERIFICACION DE DUPLICADOS")
        print("-" * 80)
        self.check_duplicates()

        print("\n8. VERIFICACION DE POOL ADDRESSES")
        print("-" * 80)
        self.check_pool_addresses()

        print("\n9. VERIFICACION DE TIMESTAMPS")
        print("-" * 80)
        self.check_timestamps()

        print("\n10. ANALISIS DE DISTRIBUCION DE LABELS")
        print("-" * 80)
        self.check_label_distribution()

        print("\n11. COMPLETITUD DE FEATURES")
        print("-" * 80)
        self.check_feature_completeness()

        print("\n12. TOKENS CON DATOS COMPLETOS PARA PREDICCION")
        print("-" * 80)
        self.check_prediction_ready_tokens()

        # Resumen final
        print("\n" + "="*80)
        print("RESUMEN DE PROBLEMAS ENCONTRADOS")
        print("="*80 + "\n")
        self.print_summary()

        return self.issues

    def check_general_stats(self):
        """Muestra estadisticas generales de la base de datos."""
        stats = self.storage.stats()
        for table, count in stats.items():
            print(f"  {table:20s}: {count:>8,} registros")
        self.add_issue("INFO", "stats", "Estadisticas generales obtenidas", count=sum(stats.values()))

    def check_chains(self):
        """Verifica que todos los tokens tengan chain valida."""
        valid_chains = ['solana', 'ethereum', 'base']

        # Tokens sin chain
        df = self.storage.query("SELECT COUNT(*) as n FROM tokens WHERE chain IS NULL OR chain = ''")
        null_count = df['n'].iloc[0]
        if null_count > 0:
            print(f"  ❌ Tokens sin chain: {null_count}")
            self.add_issue(
                "CRITICAL", "chains",
                f"{null_count} tokens sin chain definida",
                count=null_count,
                sql_fix="DELETE FROM tokens WHERE chain IS NULL OR chain = ''"
            )
        else:
            print(f"  ✓ Todos los tokens tienen chain definida")

        # Tokens con chain invalida
        placeholders = ','.join('?' * len(valid_chains))
        df = self.storage.query(
            f"SELECT chain, COUNT(*) as n FROM tokens WHERE chain NOT IN ({placeholders}) GROUP BY chain",
            tuple(valid_chains)
        )
        if not df.empty:
            for _, row in df.iterrows():
                print(f"  ❌ Chain invalida '{row['chain']}': {row['n']} tokens")
                self.add_issue(
                    "HIGH", "chains",
                    f"{row['n']} tokens con chain invalida '{row['chain']}'",
                    count=row['n'],
                    sql_fix=f"DELETE FROM tokens WHERE chain = '{row['chain']}'"
                )
        else:
            print(f"  ✓ Todas las chains son validas ({', '.join(valid_chains)})")

    def check_ohlcv_integrity(self):
        """Verifica integridad de datos OHLCV."""

        # Precios negativos
        df = self.storage.query(
            "SELECT COUNT(*) as n FROM ohlcv WHERE open < 0 OR high < 0 OR low < 0 OR close < 0"
        )
        neg_count = df['n'].iloc[0]
        if neg_count > 0:
            print(f"  ❌ Velas con precios negativos: {neg_count}")
            self.add_issue(
                "CRITICAL", "ohlcv",
                f"{neg_count} velas con precios negativos",
                count=neg_count,
                sql_fix="DELETE FROM ohlcv WHERE open < 0 OR high < 0 OR low < 0 OR close < 0"
            )
        else:
            print(f"  ✓ No hay precios negativos")

        # Volumen cero en todas las velas de un token
        df = self.storage.query("""
            SELECT token_id, COUNT(*) as n
            FROM ohlcv
            WHERE timeframe = 'day'
            GROUP BY token_id
            HAVING SUM(CASE WHEN volume > 0 THEN 1 ELSE 0 END) = 0
        """)
        if not df.empty:
            print(f"  ⚠️  Tokens con volumen=0 en TODAS las velas: {len(df)}")
            self.add_issue(
                "HIGH", "ohlcv",
                f"{len(df)} tokens tienen volumen=0 en todas sus velas",
                count=len(df),
                sql_fix="-- Revisar manualmente: puede ser pool sin actividad"
            )
        else:
            print(f"  ✓ No hay tokens con volumen=0 en todas las velas")

        # Valores NaN o NULL
        df = self.storage.query("""
            SELECT COUNT(*) as n FROM ohlcv
            WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL OR volume IS NULL
        """)
        null_count = df['n'].iloc[0]
        if null_count > 0:
            print(f"  ❌ Velas con valores NULL: {null_count}")
            self.add_issue(
                "HIGH", "ohlcv",
                f"{null_count} velas con valores NULL",
                count=null_count,
                sql_fix="DELETE FROM ohlcv WHERE open IS NULL OR high IS NULL OR low IS NULL OR close IS NULL"
            )
        else:
            print(f"  ✓ No hay valores NULL en OHLCV")

        # High < Low (imposible)
        df = self.storage.query("SELECT COUNT(*) as n FROM ohlcv WHERE high < low")
        invalid_count = df['n'].iloc[0]
        if invalid_count > 0:
            print(f"  ❌ Velas con high < low: {invalid_count}")
            self.add_issue(
                "CRITICAL", "ohlcv",
                f"{invalid_count} velas con high < low (imposible)",
                count=invalid_count,
                sql_fix="DELETE FROM ohlcv WHERE high < low"
            )
        else:
            print(f"  ✓ No hay velas con high < low")

    def check_labels_integrity(self):
        """Verifica integridad de labels."""

        # Labels sin token correspondiente
        df = self.storage.query("""
            SELECT COUNT(*) as n FROM labels l
            LEFT JOIN tokens t ON l.token_id = t.token_id
            WHERE t.token_id IS NULL
        """)
        orphan_count = df['n'].iloc[0]
        if orphan_count > 0:
            print(f"  ❌ Labels huerfanos (token no existe): {orphan_count}")
            self.add_issue(
                "HIGH", "labels",
                f"{orphan_count} labels sin token correspondiente",
                count=orphan_count,
                sql_fix="DELETE FROM labels WHERE token_id NOT IN (SELECT token_id FROM tokens)"
            )
        else:
            print(f"  ✓ Todos los labels tienen token correspondiente")

        # Labels con valores extremos sospechosos
        df = self.storage.query("""
            SELECT COUNT(*) as n FROM labels
            WHERE max_multiple > 1000 OR final_multiple > 1000 OR return_7d > 1000
        """)
        extreme_count = df['n'].iloc[0]
        if extreme_count > 0:
            print(f"  ⚠️  Labels con valores extremos (>1000x): {extreme_count}")
            self.add_issue(
                "MEDIUM", "labels",
                f"{extreme_count} labels con multiples >1000x (revisar si son reales o errores)",
                count=extreme_count,
                sql_fix="-- Revisar manualmente: SELECT * FROM labels WHERE max_multiple > 1000"
            )

        # Labels con binary que no corresponde con multi
        df = self.storage.query("""
            SELECT COUNT(*) as n FROM labels
            WHERE (label_binary = 1 AND label_multi IN ('failure', 'rug', 'pump_and_dump'))
               OR (label_binary = 0 AND label_multi IN ('gem', 'moderate_success'))
        """)
        mismatch_count = df['n'].iloc[0]
        if mismatch_count > 0:
            print(f"  ❌ Labels con binary/multi inconsistentes: {mismatch_count}")
            self.add_issue(
                "HIGH", "labels",
                f"{mismatch_count} labels con label_binary que no coincide con label_multi",
                count=mismatch_count,
                sql_fix="-- Ejecutar re-labeling: python -m scripts.relabel_tokens"
            )
        else:
            print(f"  ✓ Labels binary/multi consistentes")

    def check_features_integrity(self):
        """Verifica integridad de features."""

        try:
            df_features = self.storage.get_features_df()
            if df_features.empty:
                print(f"  ℹ️  No hay features calculados aun")
                return

            # Features sin token correspondiente
            df = self.storage.query("""
                SELECT COUNT(*) as n FROM features f
                LEFT JOIN tokens t ON f.token_id = t.token_id
                WHERE t.token_id IS NULL
            """)
            orphan_count = df['n'].iloc[0]
            if orphan_count > 0:
                print(f"  ❌ Features huerfanos (token no existe): {orphan_count}")
                self.add_issue(
                    "HIGH", "features",
                    f"{orphan_count} features sin token correspondiente",
                    count=orphan_count,
                    sql_fix="DELETE FROM features WHERE token_id NOT IN (SELECT token_id FROM tokens)"
                )
            else:
                print(f"  ✓ Todos los features tienen token correspondiente")

            # Valores extremos (>1e10 o negativos donde no deberia)
            numeric_cols = df_features.select_dtypes(include=[np.number]).columns
            outliers = []
            for col in numeric_cols:
                if col in ['token_id', 'computed_at']:
                    continue
                extreme = (df_features[col].abs() > 1e10).sum()
                if extreme > 0:
                    outliers.append((col, extreme))

            if outliers:
                print(f"  ⚠️  Features con valores extremos (>1e10):")
                for col, count in outliers[:10]:  # Mostrar primeros 10
                    print(f"      - {col}: {count} valores")
                total_extreme = sum(count for _, count in outliers)
                self.add_issue(
                    "MEDIUM", "features",
                    f"{len(outliers)} features con valores extremos",
                    count=total_extreme,
                    sql_fix="-- Revisar escalado de features y outlier handling"
                )
            else:
                print(f"  ✓ No hay valores extremos en features")

        except Exception as e:
            print(f"  ❌ Error al verificar features: {e}")
            self.add_issue("HIGH", "features", f"Error al verificar features: {e}")

    def check_orphaned_records(self):
        """Verifica registros huerfanos (sin token correspondiente)."""

        tables = [
            ('pool_snapshots', 'pool_snapshots'),
            ('ohlcv', 'ohlcv'),
            ('holder_snapshots', 'holder_snapshots'),
            ('contract_info', 'contract_info'),
        ]

        for table_name, display_name in tables:
            df = self.storage.query(f"""
                SELECT COUNT(*) as n FROM {table_name} x
                LEFT JOIN tokens t ON x.token_id = t.token_id
                WHERE t.token_id IS NULL
            """)
            orphan_count = df['n'].iloc[0]
            if orphan_count > 0:
                print(f"  ❌ {display_name} huerfanos: {orphan_count}")
                self.add_issue(
                    "HIGH", "orphans",
                    f"{orphan_count} registros en {table_name} sin token correspondiente",
                    count=orphan_count,
                    sql_fix=f"DELETE FROM {table_name} WHERE token_id NOT IN (SELECT token_id FROM tokens)"
                )
            else:
                print(f"  ✓ {display_name}: sin huerfanos")

    def check_duplicates(self):
        """Verifica duplicados de tokens (misma address, diferente chain)."""

        df = self.storage.query("""
            SELECT token_id, COUNT(DISTINCT chain) as n_chains, GROUP_CONCAT(chain) as chains
            FROM tokens
            GROUP BY token_id
            HAVING COUNT(DISTINCT chain) > 1
        """)

        if not df.empty:
            print(f"  ⚠️  Tokens duplicados (misma address, diferente chain): {len(df)}")
            for _, row in df.head(10).iterrows():
                print(f"      - {row['token_id'][:20]}... en chains: {row['chains']}")
            self.add_issue(
                "MEDIUM", "duplicates",
                f"{len(df)} tokens con misma address en multiples chains (puede ser valido si es bridge)",
                count=len(df),
                sql_fix="-- Revisar manualmente: puede ser token bridgeado o error"
            )
        else:
            print(f"  ✓ No hay duplicados de address entre chains")

    def check_pool_addresses(self):
        """Verifica pool_address en tabla tokens."""

        # Pool addresses NULL o vacios
        df = self.storage.query("""
            SELECT COUNT(*) as n FROM tokens
            WHERE pool_address IS NULL OR pool_address = ''
        """)
        null_count = df['n'].iloc[0]
        if null_count > 0:
            print(f"  ⚠️  Tokens sin pool_address: {null_count}")
            self.add_issue(
                "MEDIUM", "pools",
                f"{null_count} tokens sin pool_address definido",
                count=null_count,
                sql_fix="-- Normal para tokens recien descubiertos sin pool aun"
            )
        else:
            print(f"  ✓ Todos los tokens tienen pool_address")

        # OHLCV con pool_address vacio
        df = self.storage.query("""
            SELECT COUNT(*) as n FROM ohlcv
            WHERE pool_address IS NULL OR pool_address = ''
        """)
        ohlcv_null = df['n'].iloc[0]
        if ohlcv_null > 0:
            print(f"  ❌ OHLCV sin pool_address: {ohlcv_null}")
            self.add_issue(
                "HIGH", "pools",
                f"{ohlcv_null} registros OHLCV sin pool_address (no deberia ocurrir)",
                count=ohlcv_null,
                sql_fix="DELETE FROM ohlcv WHERE pool_address IS NULL OR pool_address = ''"
            )
        else:
            print(f"  ✓ Todos los OHLCV tienen pool_address")

    def check_timestamps(self):
        """Verifica consistencia de timestamps."""

        now = datetime.now(timezone.utc)
        future_cutoff = (now + timedelta(days=1)).isoformat()
        past_cutoff = "2024-01-01T00:00:00+00:00"

        tables_to_check = [
            ('tokens', 'first_seen'),
            ('pool_snapshots', 'snapshot_time'),
            ('ohlcv', 'timestamp'),
            ('holder_snapshots', 'snapshot_time'),
            ('labels', 'labeled_at'),
        ]

        for table, col in tables_to_check:
            # Fechas futuras
            df = self.storage.query(f"""
                SELECT COUNT(*) as n FROM {table}
                WHERE {col} > ?
            """, (future_cutoff,))
            future_count = df['n'].iloc[0]

            # Fechas antes de 2024
            df = self.storage.query(f"""
                SELECT COUNT(*) as n FROM {table}
                WHERE {col} < ?
            """, (past_cutoff,))
            past_count = df['n'].iloc[0]

            if future_count > 0:
                print(f"  ⚠️  {table}.{col}: {future_count} fechas futuras")
                self.add_issue(
                    "MEDIUM", "timestamps",
                    f"{future_count} registros en {table} con fechas futuras",
                    count=future_count
                )

            if past_count > 0:
                print(f"  ⚠️  {table}.{col}: {past_count} fechas antes de 2024")
                self.add_issue(
                    "LOW", "timestamps",
                    f"{past_count} registros en {table} con fechas antes de 2024",
                    count=past_count
                )

            if future_count == 0 and past_count == 0:
                print(f"  ✓ {table}.{col}: timestamps validos")

    def check_label_distribution(self):
        """Analiza distribucion de labels y su adecuacion para ML."""

        df = self.storage.query("""
            SELECT
                label_binary,
                COUNT(*) as n,
                ROUND(COUNT(*) * 100.0 / (SELECT COUNT(*) FROM labels), 2) as pct
            FROM labels
            GROUP BY label_binary
        """)

        if df.empty:
            print(f"  ℹ️  No hay labels aun")
            return

        print(f"  Distribucion de labels binarios:")
        for _, row in df.iterrows():
            label = "POSITIVO (gem)" if row['label_binary'] == 1 else "NEGATIVO (failure)"
            print(f"      {label}: {row['n']:>5} ({row['pct']:>5.2f}%)")

        # Verificar si hay suficientes positivos
        pos_count = df[df['label_binary'] == 1]['n'].iloc[0] if 1 in df['label_binary'].values else 0
        total = df['n'].sum()
        pos_pct = (pos_count / total * 100) if total > 0 else 0

        if pos_pct < 5:
            self.add_issue(
                "HIGH", "labels",
                f"Solo {pos_pct:.2f}% labels positivos (<5%) - considerar bajar threshold",
                count=pos_count,
                sql_fix="# En config.py: LABEL_RETURN_7D_THRESHOLD = 1.1  # Bajar de 1.5 a 1.1"
            )
        elif pos_pct < 10:
            self.add_issue(
                "MEDIUM", "labels",
                f"{pos_pct:.2f}% labels positivos (5-10%) - aceptable pero podria mejorar",
                count=pos_count
            )
        else:
            self.add_issue(
                "INFO", "labels",
                f"{pos_pct:.2f}% labels positivos (>10%) - buena distribucion",
                count=pos_count
            )

        # Distribucion multiclase
        print(f"\n  Distribucion de labels multiclase:")
        df_multi = self.storage.query("""
            SELECT label_multi, COUNT(*) as n
            FROM labels
            GROUP BY label_multi
            ORDER BY n DESC
        """)
        for _, row in df_multi.iterrows():
            print(f"      {row['label_multi']:20s}: {row['n']:>5}")

    def check_feature_completeness(self):
        """Verifica completitud de features (% NaN por columna)."""

        try:
            df_features = self.storage.get_features_df()
            if df_features.empty:
                print(f"  ℹ️  No hay features calculados aun")
                return

            # Calcular % NaN por columna
            total_rows = len(df_features)
            nan_pcts = []

            for col in df_features.columns:
                if col in ['token_id', 'computed_at']:
                    continue
                nan_count = df_features[col].isna().sum()
                nan_pct = (nan_count / total_rows * 100) if total_rows > 0 else 0
                if nan_pct > 50:
                    nan_pcts.append((col, nan_pct, nan_count))

            if nan_pcts:
                print(f"  ⚠️  Features con >50% NaN:")
                for col, pct, count in sorted(nan_pcts, key=lambda x: -x[1])[:15]:
                    print(f"      - {col:40s}: {pct:>5.1f}% ({count}/{total_rows})")
                self.add_issue(
                    "MEDIUM", "features",
                    f"{len(nan_pcts)} features con >50% NaN",
                    count=len(nan_pcts),
                    sql_fix="# Considerar excluir en config.EXCLUDED_FEATURES o mejorar calculo"
                )
            else:
                print(f"  ✓ No hay features con >50% NaN")

        except Exception as e:
            print(f"  ❌ Error al verificar completitud: {e}")

    def check_prediction_ready_tokens(self):
        """Cuenta cuantos tokens tienen TODOS los datos necesarios para prediccion."""

        # Tokens con OHLCV >= 7 dias
        df = self.storage.query("""
            SELECT token_id, COUNT(*) as n_days
            FROM (
                SELECT DISTINCT token_id, DATE(timestamp) as day
                FROM ohlcv
                WHERE timeframe = 'day'
            )
            GROUP BY token_id
            HAVING COUNT(*) >= 7
        """)
        tokens_with_ohlcv = set(df['token_id']) if not df.empty else set()

        # Tokens con pool_snapshot
        df = self.storage.query("SELECT DISTINCT token_id FROM pool_snapshots")
        tokens_with_pool = set(df['token_id']) if not df.empty else set()

        # Tokens con features
        df = self.storage.query("SELECT token_id FROM features")
        tokens_with_features = set(df['token_id']) if not df.empty else set()

        # Tokens con labels
        df = self.storage.query("SELECT token_id FROM labels")
        tokens_with_labels = set(df['token_id']) if not df.empty else set()

        # Interseccion: tokens con TODO
        ready_for_prediction = tokens_with_ohlcv & tokens_with_pool & tokens_with_features
        ready_for_training = ready_for_prediction & tokens_with_labels

        print(f"  Tokens con OHLCV >= 7 dias: {len(tokens_with_ohlcv):>6,}")
        print(f"  Tokens con pool_snapshot:   {len(tokens_with_pool):>6,}")
        print(f"  Tokens con features:        {len(tokens_with_features):>6,}")
        print(f"  Tokens con labels:          {len(tokens_with_labels):>6,}")
        print(f"  ━" * 40)
        print(f"  Tokens listos para PREDICCION: {len(ready_for_prediction):>6,}")
        print(f"  Tokens listos para TRAINING:   {len(ready_for_training):>6,}")

        self.add_issue(
            "INFO", "completeness",
            f"{len(ready_for_prediction)} tokens listos para prediccion, {len(ready_for_training)} para training"
        )

        # Porcentaje de utilizacion
        total_tokens = self.storage.query("SELECT COUNT(*) as n FROM tokens")['n'].iloc[0]
        if total_tokens > 0:
            pct_ready = (len(ready_for_prediction) / total_tokens * 100)
            print(f"\n  Tasa de aprovechamiento: {pct_ready:.1f}% ({len(ready_for_prediction)}/{total_tokens})")

            if pct_ready < 30:
                self.add_issue(
                    "MEDIUM", "completeness",
                    f"Solo {pct_ready:.1f}% tokens aprovechables - necesitan madurar mas datos",
                    sql_fix="# Esperar mas dias para que OHLCV madure (7-30 dias)"
                )

    def print_summary(self):
        """Imprime resumen de problemas encontrados."""

        # Agrupar por severidad
        by_severity = {}
        for issue in self.issues:
            sev = issue['severity']
            if sev not in by_severity:
                by_severity[sev] = []
            by_severity[sev].append(issue)

        # Orden de severidad
        severity_order = ['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']

        for severity in severity_order:
            if severity not in by_severity:
                continue

            issues = by_severity[severity]
            print(f"\n{severity} ({len(issues)} problemas)")
            print("-" * 80)

            for i, issue in enumerate(issues, 1):
                desc = issue['description']
                count = issue.get('count')
                if count:
                    desc += f" (n={count:,})"
                print(f"  {i}. {desc}")

                if issue.get('sql_fix'):
                    print(f"     Fix: {issue['sql_fix']}")

        # Totales
        print("\n" + "="*80)
        critical = len(by_severity.get('CRITICAL', []))
        high = len(by_severity.get('HIGH', []))
        medium = len(by_severity.get('MEDIUM', []))

        if critical > 0:
            print(f"⚠️  ATENCION: {critical} problemas CRITICOS que requieren accion inmediata")
        if high > 0:
            print(f"⚠️  {high} problemas de prioridad ALTA")
        if medium > 0:
            print(f"ℹ️  {medium} problemas de prioridad MEDIA")

        if critical == 0 and high == 0:
            print("✅ No se encontraron problemas criticos o de alta prioridad")


if __name__ == "__main__":
    auditor = DataIntegrityAuditor()
    issues = auditor.run_all_checks()

    print(f"\n\nAuditoria completada. Total de issues: {len(issues)}")
