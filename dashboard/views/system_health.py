"""
system_health.py - Pagina de estado del sistema y monitoreo.

Muestra:
- Estado de health checks (APIs, DB, disco, recopilacion, API usage)
- Graficos de uso de APIs (consumo mensual, trending diario)
- Timestamps de ultima ejecucion (collect, backup, health check)
- Estadisticas de espacio en disco
- Estado de servicios launchd
"""
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime, timedelta, timezone
import json
import subprocess

from src.data.storage import Storage

# Constantes
LOGS_DIR = Path("logs")
HEALTH_STATUS_FILE = LOGS_DIR / "health_status.json"
API_LIMITS = {
    "coingecko": 10000,      # Demo API: 10K calls/month
    "geckoterminal": None,   # No limit (30/min)
    "dexscreener": None,     # No limit (300/min)
    "helius": None,          # Free tier: 50 calls/sec
    "etherscan": None,       # Free tier: 5 calls/sec (100K/day)
}


@st.cache_resource
def get_storage():
    """Crea una instancia de Storage cacheada para no reconectar cada vez."""
    return Storage()


def render():
    """Renderiza la pagina de System Health."""
    st.title("🏥 System Health - Estado del Sistema")

    st.info(
        "**Que es esto?** Esta pagina muestra el estado de salud del sistema "
        "de Trading Memes. Aqui puedes ver si todo esta funcionando correctamente, "
        "monitorear el uso de APIs, verificar cuando fue la ultima recopilacion, "
        "y revisar el espacio disponible en disco.\n\n"
        "**Para que sirve?** Te ayuda a detectar problemas antes de que afecten "
        "la recopilacion de datos, y te alerta si estas cerca de los limites de "
        "las APIs gratuitas."
    )

    # Tabs
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "Estado General",
        "Uso de APIs",
        "Servicios y Logs",
        "Espacio en Disco",
        "Ejecutar Scripts",
    ])

    with tab1:
        render_general_health()

    with tab2:
        render_api_usage()

    with tab3:
        render_services_logs()

    with tab4:
        render_disk_space()

    with tab5:
        render_execute_scripts()


def render_general_health():
    """Renderiza el estado general del sistema."""
    st.subheader("Estado General del Sistema")

    # Intentar cargar el ultimo health check
    health_data = load_latest_health_status()

    if not health_data:
        st.warning(
            "No hay datos de health check disponibles. "
            "Ejecuta `./scripts/health_check.sh` para generar el primer reporte."
        )
        return

    # Timestamp del ultimo check
    timestamp_str = health_data.get("timestamp", "Unknown")
    try:
        timestamp = datetime.fromisoformat(timestamp_str.replace("Z", "+00:00"))
        st.caption(f"Ultimo health check: **{timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}**")
    except Exception:
        st.caption(f"Ultimo health check: **{timestamp_str}**")

    # Estado global
    all_ok = health_data.get("all_ok", False)
    if all_ok:
        st.success("✅ **Todos los sistemas operativos**")
    else:
        st.error("❌ **Hay problemas detectados** - Revisa los detalles abajo")

    st.divider()

    # Detalles de cada check
    checks = health_data.get("checks", {})

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("### 🌐 APIs")
        render_check_status(checks.get("apis", {}))

        st.markdown("### 🗄️ Base de Datos")
        render_check_status(checks.get("database", {}))

        st.markdown("### ⏰ Recopilacion")
        render_check_status(checks.get("collection", {}))

    with col2:
        st.markdown("### 💾 Espacio en Disco")
        render_check_status(checks.get("disk_space", {}))

        st.markdown("### 📊 Uso de APIs")
        render_check_status(checks.get("api_usage", {}))


def render_check_status(check_data: dict):
    """Renderiza el estado de un check individual."""
    if not check_data:
        st.info("No hay datos disponibles para este check.")
        return

    status = check_data.get("status", "unknown")
    message = check_data.get("message", "Sin mensaje")

    if status == "ok":
        st.success(f"✅ {message}")
    elif status == "warning":
        st.warning(f"⚠️ {message}")
    elif status == "error":
        st.error(f"❌ {message}")
    else:
        st.info(f"ℹ️ {message}")

    # Detalles adicionales
    details = check_data.get("details", {})
    if details:
        with st.expander("Ver detalles"):
            st.json(details)


def render_api_usage():
    """Renderiza graficos de uso de APIs."""
    st.subheader("📊 Uso de APIs")
    st.caption(
        "Monitoreo del consumo de APIs. Algunos servicios tienen limites "
        "mensuales (ej: CoinGecko Demo = 10K calls/mes). "
        "Esta seccion te ayuda a evitar exceder esos limites."
    )

    storage = get_storage()

    # Obtener estadisticas de uso en los ultimos 30 dias
    usage_stats = storage.get_api_usage_stats(days=30)

    if usage_stats.empty:
        st.info(
            "No hay datos de uso de APIs todavia. "
            "El tracking se activo recientemente y se ira acumulando con el tiempo."
        )
        return

    # Resumen por API
    summary = usage_stats.groupby("api_name").size().reset_index(name="total_calls")

    st.markdown("### Resumen de llamadas (ultimos 30 dias)")

    # Metricas por API
    cols = st.columns(len(summary))
    for idx, row in summary.iterrows():
        api_name = row["api_name"]
        total_calls = row["total_calls"]
        limit = API_LIMITS.get(api_name)

        with cols[idx]:
            if limit:
                pct_used = (total_calls / limit) * 100
                st.metric(
                    api_name.capitalize(),
                    f"{total_calls:,}",
                    delta=f"{pct_used:.1f}% del limite",
                    delta_color="inverse" if pct_used > 80 else "off"
                )
            else:
                st.metric(api_name.capitalize(), f"{total_calls:,}")

    st.divider()

    # Grafico de barras: llamadas por API
    st.markdown("### Distribucion de llamadas por API")
    fig_bar = px.bar(
        summary,
        x="api_name",
        y="total_calls",
        title="Total de llamadas por API (ultimos 30 dias)",
        labels={"api_name": "API", "total_calls": "Total de Llamadas"},
        color="api_name",
        color_discrete_sequence=px.colors.qualitative.Set2,
    )
    fig_bar.update_layout(showlegend=False, height=350)
    st.plotly_chart(fig_bar, use_container_width=True)

    # Grafico de linea: trending diario
    st.markdown("### Trending diario de llamadas")

    usage_by_day = storage.get_api_usage_by_day(days=30)

    if not usage_by_day.empty:
        # Parsear fecha
        usage_by_day["date"] = pd.to_datetime(usage_by_day["date"])

        fig_line = px.line(
            usage_by_day,
            x="date",
            y="call_count",
            color="api_name",
            title="Llamadas diarias por API",
            labels={"date": "Fecha", "call_count": "Llamadas", "api_name": "API"},
            markers=True,
        )
        fig_line.update_layout(height=400)
        st.plotly_chart(fig_line, use_container_width=True)
    else:
        st.info("No hay suficientes datos para mostrar trending diario.")

    # Tabla detallada
    with st.expander("Ver tabla completa de uso"):
        st.dataframe(usage_stats, use_container_width=True, hide_index=True)


def render_services_logs():
    """Renderiza el estado de servicios launchd y logs."""
    st.subheader("⚙️ Servicios y Logs")
    st.caption(
        "Estado de los servicios automatizados (launchd) y acceso rapido a los logs. "
        "Los servicios deben estar activos para que la recopilacion y backups funcionen."
    )

    # Estado de servicios launchd
    st.markdown("### Servicios Activos (launchd)")

    services = [
        ("com.tradingmemes.dailycollect", "Daily Collect (03:00)"),
        ("com.tradingmemes.healthcheck", "Health Check (cada 6h)"),
        ("com.tradingmemes.backup", "Backup (04:00)"),
    ]

    for service_id, service_name in services:
        is_active = check_launchd_service(service_id)
        if is_active:
            st.success(f"✅ **{service_name}** - Activo")
        else:
            st.error(f"❌ **{service_name}** - Inactivo")
            st.caption(
                f"Para activar: `launchctl load ~/Library/LaunchAgents/{service_id}.plist`"
            )

    st.divider()

    # Logs recientes
    st.markdown("### Logs Recientes")

    log_files = {
        "Health Check": LOGS_DIR / "health_check.log",
        "Backup": LOGS_DIR / "backup.log",
        "Collector": LOGS_DIR / "collector.log",
    }

    selected_log = st.selectbox(
        "Selecciona un log para ver",
        options=list(log_files.keys()),
        help="Muestra las ultimas 50 lineas del log seleccionado."
    )

    log_path = log_files[selected_log]

    if log_path.exists():
        try:
            with open(log_path, "r") as f:
                lines = f.readlines()
                last_lines = lines[-50:]  # Ultimas 50 lineas
                log_text = "".join(last_lines)
                st.code(log_text, language="log")
        except Exception as e:
            st.error(f"Error leyendo log: {e}")
    else:
        st.info(f"El archivo de log no existe todavia: {log_path}")


def render_disk_space():
    """Renderiza informacion de espacio en disco."""
    st.subheader("💾 Espacio en Disco")
    st.caption(
        "Monitoreo del espacio disponible y uso del proyecto. "
        "Se requiere al menos 5GB libres para operacion normal."
    )

    # Obtener espacio disponible con df
    try:
        result = subprocess.run(
            ["df", "-h", "."],
            capture_output=True,
            text=True,
            check=True
        )
        df_output = result.stdout.strip().split("\n")
        if len(df_output) >= 2:
            fields = df_output[1].split()
            size = fields[1]
            used = fields[2]
            avail = fields[3]
            use_pct = fields[4]

            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Tamaño Total", size)
            col2.metric("Usado", used)
            col3.metric("Disponible", avail)
            col4.metric("Uso %", use_pct)

            # Alerta si queda poco espacio
            use_pct_num = int(use_pct.replace("%", ""))
            if use_pct_num > 90:
                st.error("⚠️ **Espacio critico** - Menos del 10% disponible")
            elif use_pct_num > 80:
                st.warning("⚠️ **Espacio bajo** - Considera limpiar archivos antiguos")
            else:
                st.success("✅ Espacio en disco suficiente")
        else:
            st.warning("No se pudo parsear el output de df")

    except Exception as e:
        st.error(f"Error obteniendo espacio en disco: {e}")

    st.divider()

    # Tamano del proyecto
    st.markdown("### Tamano del Proyecto")

    project_root = Path(".")
    directories = {
        "Base de Datos (data/)": project_root / "data" / "trading_memes.db",
        "Backups (data/backups/)": project_root / "data" / "backups",
        "Raw Data (data/raw/)": project_root / "data" / "raw",
        "Models (data/models/)": project_root / "data" / "models",
        "Processed (data/processed/)": project_root / "data" / "processed",
        "Cache (.cache/)": project_root / ".cache",
    }

    sizes = []
    for name, path in directories.items():
        if path.exists():
            if path.is_file():
                size_bytes = path.stat().st_size
            else:
                # Calcular tamano recursivo de directorio
                size_bytes = sum(
                    f.stat().st_size
                    for f in path.rglob("*")
                    if f.is_file()
                )

            # Convertir a formato human-readable
            size_mb = size_bytes / (1024 * 1024)
            sizes.append({"Directorio": name, "Tamano (MB)": round(size_mb, 2)})

    if sizes:
        df_sizes = pd.DataFrame(sizes)
        st.dataframe(df_sizes, use_container_width=True, hide_index=True)

        # Grafico de pastel
        fig_pie = px.pie(
            df_sizes,
            names="Directorio",
            values="Tamano (MB)",
            title="Distribucion de espacio por directorio",
        )
        fig_pie.update_layout(height=400)
        st.plotly_chart(fig_pie, use_container_width=True)
    else:
        st.info("No se encontraron directorios para analizar.")


def render_execute_scripts():
    """Renderiza la seccion de ejecucion de scripts."""
    st.subheader("🚀 Ejecutar Scripts")
    st.caption(
        "Ejecuta los scripts principales del proyecto directamente desde el dashboard. "
        "Útil para ejecutar tareas manuales sin tener que abrir la terminal.\n\n"
        "**⚠️ IMPORTANTE**: Algunos scripts pueden tardar varios minutos en completarse. "
        "El dashboard se bloqueará mientras se ejecuta el script."
    )

    st.divider()

    # Scripts disponibles
    scripts = {
        "Health Check": {
            "path": "./scripts/health_check.sh",
            "description": "Ejecuta una verificación completa del sistema (APIs, DB, disco, recopilación, API usage)",
            "icon": "🏥",
            "duration": "~30 segundos",
            "type": "primary",
        },
        "Quick Stats": {
            "path": "./scripts/quick_stats.sh",
            "description": "Muestra estadísticas rápidas del sistema (DB, última recopilación, espacio, modelos, backups)",
            "icon": "📊",
            "duration": "~10 segundos",
            "type": "secondary",
        },
        "Backup DB": {
            "path": "./scripts/backup_db.sh",
            "description": "Crea un backup manual de la base de datos (SQLite + Parquet + metadata)",
            "icon": "💾",
            "duration": "~1-2 minutos",
            "type": "secondary",
        },
        "Test System": {
            "path": "./scripts/test_system.sh",
            "description": "Ejecuta 9 secciones de verificación completa del sistema",
            "icon": "🧪",
            "duration": "~1 minuto",
            "type": "secondary",
        },
        "Daily Collect": {
            "path": "./scripts/daily_collect.sh",
            "description": "⚠️ Ejecuta recopilación manual de datos de APIs. SOLO usar si el cron falló.",
            "icon": "🔄",
            "duration": "~5-10 minutos",
            "type": "secondary",
        },
        "Re-entrenar Modelos": {
            "path": "./scripts/retrain.sh",
            "description": "⚠️ Re-entrena los modelos ML con los datos actuales. SOLO ejecutar cuando haya nuevos datos.",
            "icon": "🤖",
            "duration": "~2-5 minutos",
            "type": "secondary",
        },
    }

    # Mostrar scripts en columnas
    col1, col2 = st.columns(2)

    for idx, (script_name, script_info) in enumerate(scripts.items()):
        col = col1 if idx % 2 == 0 else col2

        with col:
            st.markdown(f"### {script_info['icon']} {script_name}")
            st.caption(script_info["description"])
            st.caption(f"⏱️ Duración estimada: **{script_info['duration']}**")

            button_key = f"btn_{script_name.replace(' ', '_').lower()}"
            button_type = script_info["type"]

            if st.button(
                f"Ejecutar {script_name}",
                key=button_key,
                type=button_type,
                use_container_width=True
            ):
                execute_script(script_name, script_info["path"])

            st.divider()

    # Nota de seguridad
    st.warning(
        "⚠️ **Nota de seguridad**: Los scripts se ejecutan con los permisos del usuario que lanzó "
        "el dashboard. Asegúrate de entender qué hace cada script antes de ejecutarlo."
    )


def execute_script(script_name: str, script_path: str):
    """Ejecuta un script y muestra el output en el dashboard."""
    st.info(f"Ejecutando **{script_name}**... Por favor espera.")

    # Crear placeholder para mostrar progreso
    output_placeholder = st.empty()

    try:
        # Ejecutar script
        result = subprocess.run(
            ["bash", script_path],
            capture_output=True,
            text=True,
            timeout=600,  # 10 minutos max
            cwd=Path(".").resolve(),
        )

        # Mostrar output
        if result.returncode == 0:
            st.success(f"✅ **{script_name}** ejecutado exitosamente")
        else:
            st.error(f"❌ **{script_name}** falló con código {result.returncode}")

        # Mostrar stdout
        if result.stdout:
            with st.expander("📄 Output del script", expanded=True):
                st.code(result.stdout, language="bash")

        # Mostrar stderr si hay errores
        if result.stderr:
            with st.expander("⚠️ Errores y warnings"):
                st.code(result.stderr, language="bash")

    except subprocess.TimeoutExpired:
        st.error(f"⏱️ **{script_name}** excedió el tiempo límite de 10 minutos")
    except FileNotFoundError:
        st.error(f"❌ Script no encontrado: {script_path}")
    except Exception as e:
        st.error(f"❌ Error ejecutando {script_name}: {e}")


# ============================================================
# FUNCIONES AUXILIARES
# ============================================================

def load_latest_health_status() -> dict:
    """Carga el ultimo health status JSON."""
    if not HEALTH_STATUS_FILE.exists():
        return {}

    try:
        with open(HEALTH_STATUS_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def check_launchd_service(service_id: str) -> bool:
    """Verifica si un servicio launchd esta activo."""
    try:
        result = subprocess.run(
            ["launchctl", "list"],
            capture_output=True,
            text=True,
            check=True
        )
        return service_id in result.stdout
    except Exception:
        return False
