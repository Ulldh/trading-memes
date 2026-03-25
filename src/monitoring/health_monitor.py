"""
health_monitor.py - Monitor de salud del sistema Trading Memes.

Este modulo verifica que todos los componentes del sistema funcionen correctamente:
- APIs disponibles y respondiendo
- Base de datos accesible y creciendo
- Espacio en disco suficiente
- Logs sin errores criticos recientes
- Ultima ejecucion de recoleccion exitosa

Uso:
    from src.monitoring import HealthMonitor

    monitor = HealthMonitor()
    status = monitor.check_all()

    if not status["healthy"]:
        print("ALERTA:", status["issues"])
"""

import json
import os
import shutil
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
import pandas as pd

from src.data.supabase_storage import get_storage
from src.api import CoinGeckoClient, DexScreenerClient, SolanaRPC, EtherscanClient
from src.utils.logger import get_logger

try:
    from config import DB_PATH, PROJECT_ROOT, SUPPORTED_CHAINS
except ImportError:
    DB_PATH = Path("data/trading_memes.db")
    PROJECT_ROOT = Path.cwd()
    SUPPORTED_CHAINS = {"solana": {}, "ethereum": {}, "base": {}}

logger = get_logger(__name__)


class HealthMonitor:
    """
    Monitor de salud del sistema.

    Ejecuta verificaciones periodicas para detectar problemas antes
    de que causen fallas en produccion.

    Cada metodo check_* retorna un dict con:
        {
            "status": "ok" | "warning" | "error",
            "message": str,
            "details": dict (opcional)
        }

    Ejemplo:
        monitor = HealthMonitor()

        # Verificacion completa
        result = monitor.check_all()
        print(f"Sistema saludable: {result['healthy']}")

        # Verificacion individual
        api_status = monitor.check_apis()
        print(api_status)
    """

    def __init__(
        self,
        storage=None,
        min_disk_gb: float = 1.0,
        max_hours_since_collection: int = 26,  # 24h + margen de 2h
    ):
        """
        Inicializa el monitor de salud.

        Args:
            storage: Instancia de Storage. Si no se pasa, se crea una nueva.
            min_disk_gb: Espacio minimo requerido en disco (GB).
            max_hours_since_collection: Horas maximas desde ultima recoleccion.
        """
        self.storage = storage or get_storage()
        self.min_disk_gb = min_disk_gb
        self.max_hours_since_collection = max_hours_since_collection

        # Inicializar clientes API
        self.api_clients = {
            "geckoterminal": CoinGeckoClient(),
            "dexscreener": DexScreenerClient(),
            "solana_rpc": SolanaRPC(),
            "etherscan": EtherscanClient(),
        }

    def check_all(self) -> Dict[str, Any]:
        """
        Ejecuta todas las verificaciones de salud.

        Returns:
            dict con estructura:
            {
                "healthy": bool,
                "timestamp": str (ISO 8601),
                "checks": {
                    "apis": {...},
                    "database": {...},
                    "disk": {...},
                    "collection": {...}
                },
                "issues": [str, ...],  # Lista de problemas encontrados
                "warnings": [str, ...]  # Lista de warnings
            }
        """
        logger.info("Iniciando verificacion de salud del sistema")

        checks = {
            "apis": self.check_apis(),
            "database": self.check_database(),
            "disk": self.check_disk_space(),
            "collection": self.check_last_collection(),
            "api_usage": self.check_api_usage(),
            "model_drift": self.check_model_drift(),
        }

        # Recopilar issues y warnings
        issues = []
        warnings = []

        for check_name, check_result in checks.items():
            if check_result["status"] == "error":
                issues.append(f"{check_name}: {check_result['message']}")
            elif check_result["status"] == "warning":
                warnings.append(f"{check_name}: {check_result['message']}")

        healthy = len(issues) == 0

        result = {
            "healthy": healthy,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "issues": issues,
            "warnings": warnings,
        }

        if healthy:
            logger.info("✓ Sistema saludable - Todas las verificaciones pasaron")
        else:
            logger.error(f"✗ Sistema con problemas: {len(issues)} errores, {len(warnings)} warnings")

        return result

    def check_apis(self) -> Dict[str, Any]:
        """
        Verifica que todas las APIs esten respondiendo correctamente.

        Hace una llamada simple a cada API para verificar conectividad.

        Returns:
            dict con status, message y details de cada API.
        """
        logger.info("Verificando APIs...")

        api_results = {}
        errors = []

        # GeckoTerminal - Probar con Solana trending
        try:
            data = self.api_clients["geckoterminal"].get_trending_pools(chain="solana")
            api_results["geckoterminal"] = {
                "status": "ok" if data else "error",
            }
            if not data:
                errors.append("GeckoTerminal no retorno datos")
        except Exception as e:
            api_results["geckoterminal"] = {"status": "error", "error": str(e)}
            errors.append(f"GeckoTerminal: {str(e)[:100]}")

        # DexScreener - Probar endpoint de tokens con boost
        try:
            data = self.api_clients["dexscreener"].get_token_profiles()
            api_results["dexscreener"] = {
                "status": "ok" if data else "warning",
            }
        except Exception as e:
            api_results["dexscreener"] = {"status": "error", "error": str(e)}
            errors.append(f"DexScreener: {str(e)[:100]}")

        # Solana RPC - Probar con token supply de Wrapped SOL
        try:
            test_address = "So11111111111111111111111111111111111111112"
            data = self.api_clients["solana_rpc"].get_token_largest_accounts(test_address)
            api_results["solana_rpc"] = {
                "status": "ok" if data is not None else "error",
            }
            if data is None:
                errors.append("Solana RPC no respondio")
        except Exception as e:
            api_results["solana_rpc"] = {"status": "error", "error": str(e)}
            errors.append(f"Solana RPC: {str(e)[:100]}")

        # Etherscan - Probar con USDT en Ethereum
        try:
            test_address = "0xdac17f958d2ee523a2206206994597c13d831ec7"
            data = self.api_clients["etherscan"].get_contract_source(test_address)
            api_results["etherscan"] = {
                "status": "ok" if data else "warning",
            }
        except Exception as e:
            api_results["etherscan"] = {"status": "error", "error": str(e)}
            errors.append(f"Etherscan: {str(e)[:100]}")

        # Determinar status general
        if len(errors) == 0:
            status = "ok"
            message = "Todas las APIs respondiendo correctamente"
        elif len(errors) < len(api_results):
            status = "warning"
            message = f"{len(errors)}/{len(api_results)} APIs con problemas"
        else:
            status = "error"
            message = "Todas las APIs fallando"

        return {
            "status": status,
            "message": message,
            "details": api_results,
            "errors": errors,
        }

    def check_database(self) -> Dict[str, Any]:
        """
        Verifica que la base de datos este accesible y creciendo.

        Comprueba:
        - DB existe y es accesible
        - Tiene datos (no esta vacia)
        - Ha crecido en las ultimas 48h (al menos 1 nuevo registro OHLCV)

        Returns:
            dict con status, message y estadisticas de la DB.
        """
        logger.info("Verificando base de datos...")

        try:
            # Verificar que existe
            if not DB_PATH.exists():
                return {
                    "status": "error",
                    "message": f"Base de datos no existe: {DB_PATH}",
                }

            # Obtener estadisticas
            stats = self.storage.stats()

            # Verificar que tiene datos
            if stats["tokens"] == 0:
                return {
                    "status": "error",
                    "message": "Base de datos vacia (0 tokens)",
                    "stats": stats,
                }

            # Verificar crecimiento reciente (ultimas 48h)
            # Query para contar registros OHLCV de ultimas 48h
            cutoff = datetime.now(timezone.utc) - timedelta(hours=48)
            cutoff_str = cutoff.isoformat()

            query = """
                SELECT COUNT(*) as count
                FROM ohlcv
                WHERE timestamp >= ?
            """

            result_df = self.storage.query(query, (cutoff_str,))
            recent_count = int(result_df.iloc[0]["count"]) if not result_df.empty else 0

            if recent_count == 0:
                return {
                    "status": "warning",
                    "message": "Base de datos no ha crecido en ultimas 48h",
                    "stats": stats,
                    "recent_ohlcv": recent_count,
                }

            # Todo OK
            return {
                "status": "ok",
                "message": f"Base de datos saludable ({stats['tokens']} tokens, {recent_count} OHLCV recientes)",
                "stats": stats,
                "recent_ohlcv": recent_count,
            }

        except Exception as e:
            logger.error(f"Error verificando base de datos: {e}")
            return {
                "status": "error",
                "message": f"Error accediendo a base de datos: {str(e)[:100]}",
            }

    def check_disk_space(self) -> Dict[str, Any]:
        """
        Verifica que haya suficiente espacio en disco.

        Returns:
            dict con status, message y espacio disponible.
        """
        logger.info("Verificando espacio en disco...")

        try:
            # Obtener estadisticas de disco del proyecto
            disk_usage = shutil.disk_usage(PROJECT_ROOT)

            free_gb = disk_usage.free / (1024 ** 3)  # Convertir a GB
            total_gb = disk_usage.total / (1024 ** 3)
            used_gb = disk_usage.used / (1024 ** 3)
            percent_used = (used_gb / total_gb) * 100

            if free_gb < self.min_disk_gb:
                return {
                    "status": "error",
                    "message": f"Espacio en disco critico: {free_gb:.2f} GB libres",
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "percent_used": percent_used,
                }
            elif free_gb < self.min_disk_gb * 2:
                return {
                    "status": "warning",
                    "message": f"Espacio en disco bajo: {free_gb:.2f} GB libres",
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "percent_used": percent_used,
                }
            else:
                return {
                    "status": "ok",
                    "message": f"Espacio en disco suficiente: {free_gb:.2f} GB libres",
                    "free_gb": free_gb,
                    "total_gb": total_gb,
                    "percent_used": percent_used,
                }

        except Exception as e:
            logger.error(f"Error verificando espacio en disco: {e}")
            return {
                "status": "error",
                "message": f"Error verificando disco: {str(e)}",
            }

    def check_last_collection(self) -> Dict[str, Any]:
        """
        Verifica que la recoleccion diaria este ejecutandose.

        Busca el registro OHLCV mas reciente y verifica que no sea
        demasiado antiguo (>26h).

        Returns:
            dict con status, message y timestamp de ultima recoleccion.
        """
        logger.info("Verificando ultima recoleccion...")

        try:
            # Query para obtener el timestamp mas reciente de OHLCV
            query = """
                SELECT MAX(timestamp) as last_timestamp
                FROM ohlcv
            """

            result_df = self.storage.query(query)

            if result_df.empty or pd.isna(result_df.iloc[0]["last_timestamp"]):
                return {
                    "status": "error",
                    "message": "No hay registros OHLCV en la base de datos",
                }

            last_timestamp_str = result_df.iloc[0]["last_timestamp"]
            last_timestamp = datetime.fromisoformat(last_timestamp_str.replace('Z', '+00:00'))
            now = datetime.now(timezone.utc)
            hours_since = (now - last_timestamp).total_seconds() / 3600

            if hours_since > self.max_hours_since_collection:
                return {
                    "status": "error",
                    "message": f"Ultima recoleccion hace {hours_since:.1f} horas (>26h)",
                    "last_collection": last_timestamp.isoformat(),
                    "hours_since": hours_since,
                }
            elif hours_since > 24:
                return {
                    "status": "warning",
                    "message": f"Ultima recoleccion hace {hours_since:.1f} horas",
                    "last_collection": last_timestamp.isoformat(),
                    "hours_since": hours_since,
                }
            else:
                return {
                    "status": "ok",
                    "message": f"Recoleccion reciente (hace {hours_since:.1f} horas)",
                    "last_collection": last_timestamp.isoformat(),
                    "hours_since": hours_since,
                }

        except Exception as e:
            logger.error(f"Error verificando ultima recoleccion: {e}")
            return {
                "status": "error",
                "message": f"Error verificando recoleccion: {str(e)[:100]}",
            }

    def check_api_usage(self) -> Dict[str, Any]:
        """
        Verifica el uso de APIs y alerta si se acerca a los límites.

        Límites conocidos:
        - CoinGecko (demo): 10,000 calls/mes
        - GeckoTerminal: Sin límite documentado
        - DexScreener: Sin límite documentado
        - Helius (free): Sin límite estricto
        - Etherscan (free): Sin límite mensual estricto

        Returns:
            dict con status, message y usage stats por API.
        """
        logger.info("Verificando uso de APIs...")

        # Límites mensuales conocidos
        MONTHLY_LIMITS = {
            "coingecko": 10000,  # Demo API
            "geckoterminal": None,  # Sin límite documentado
            "dexscreener": None,
            "helius": None,
            "etherscan": None,
        }

        try:
            # Obtener estadísticas de últimos 30 días
            stats_df = self.storage.get_api_usage_stats(days=30)

            if stats_df.empty:
                return {
                    "status": "ok",
                    "message": "No hay datos de uso de APIs (tracking recién iniciado)",
                }

            # Convertir a dict para análisis
            stats_by_api = {}
            for _, row in stats_df.iterrows():
                api_name = row["api_name"]
                total_calls = int(row["total_calls"])
                limit = MONTHLY_LIMITS.get(api_name)

                stats_by_api[api_name] = {
                    "total_calls": total_calls,
                    "limit": limit,
                    "pct_used": (total_calls / limit * 100) if limit else None,
                }

            # Detectar problemas
            warnings = []
            errors = []

            for api_name, data in stats_by_api.items():
                if data["limit"] and data["pct_used"]:
                    if data["pct_used"] >= 90:
                        errors.append(
                            f"{api_name}: {data['total_calls']}/{data['limit']} calls "
                            f"({data['pct_used']:.1f}%) - LÍMITE CASI ALCANZADO"
                        )
                    elif data["pct_used"] >= 80:
                        warnings.append(
                            f"{api_name}: {data['total_calls']}/{data['limit']} calls "
                            f"({data['pct_used']:.1f}%) - cerca del límite"
                        )

            # Determinar status
            if errors:
                status = "error"
                message = f"{len(errors)} API(s) cerca del límite mensual"
            elif warnings:
                status = "warning"
                message = f"{len(warnings)} API(s) usando >80% del límite"
            else:
                status = "ok"
                message = "Uso de APIs dentro de límites normales"

            return {
                "status": status,
                "message": message,
                "stats": stats_by_api,
                "warnings": warnings,
                "errors": errors,
            }

        except Exception as e:
            logger.error(f"Error verificando uso de APIs: {e}")
            return {
                "status": "ok",  # No fallar health check por esto
                "message": "No se pudo verificar uso de APIs (tracking deshabilitado)",
            }

    def check_model_drift(self) -> Dict[str, Any]:
        """
        Verifica si el modelo necesita re-entrenamiento usando DriftDetector.

        Detecta tres tipos de drift:
        - Data drift: Distribucion de features cambio significativamente.
        - Concept drift: F1 score degradado.
        - Volume drift: Suficientes tokens nuevos para re-entrenar.

        Returns:
            dict con status, message y detalles del drift detectado.
        """
        logger.info("Verificando model drift...")

        try:
            from src.models.drift_detector import DriftDetector

            detector = DriftDetector()
            drift_results = detector.detect_all_drift()

            if drift_results is None:
                return {
                    "status": "ok",
                    "message": "No hay modelo entrenado para verificar drift",
                }

            # Evaluar resultados de drift
            needs_retrain = drift_results.get("needs_retrain", False)
            drift_types = drift_results.get("drift_types", [])

            if needs_retrain:
                return {
                    "status": "warning",
                    "message": f"Modelo necesita re-entrenamiento: {', '.join(drift_types)}",
                    "details": drift_results,
                }
            else:
                return {
                    "status": "ok",
                    "message": "Modelo sin drift significativo",
                    "details": drift_results,
                }

        except ImportError:
            return {
                "status": "ok",
                "message": "DriftDetector no disponible (modulo no encontrado)",
            }
        except Exception as e:
            logger.warning(f"Error verificando model drift: {e}")
            return {
                "status": "ok",  # No fallar health check por esto
                "message": f"No se pudo verificar drift: {str(e)[:100]}",
            }

    def get_summary(self) -> str:
        """
        Genera un resumen legible del estado del sistema.

        Returns:
            str con resumen en formato texto para enviar por email/Telegram.
        """
        status = self.check_all()

        lines = [
            "=" * 50,
            "HEALTH CHECK - Trading Memes",
            "=" * 50,
            f"Timestamp: {status['timestamp']}",
            f"Estado: {'✓ SALUDABLE' if status['healthy'] else '✗ PROBLEMAS DETECTADOS'}",
            "",
        ]

        if status["issues"]:
            lines.append("ERRORES:")
            for issue in status["issues"]:
                lines.append(f"  ✗ {issue}")
            lines.append("")

        if status["warnings"]:
            lines.append("WARNINGS:")
            for warning in status["warnings"]:
                lines.append(f"  ⚠ {warning}")
            lines.append("")

        lines.append("DETALLES:")
        for check_name, check_result in status["checks"].items():
            icon = "✓" if check_result["status"] == "ok" else "✗" if check_result["status"] == "error" else "⚠"
            lines.append(f"  {icon} {check_name}: {check_result['message']}")

        lines.append("=" * 50)

        return "\n".join(lines)


if __name__ == "__main__":
    # Test rapido
    monitor = HealthMonitor()
    print(monitor.get_summary())
