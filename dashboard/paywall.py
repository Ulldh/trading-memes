"""
paywall.py — Componente de paywall para features premium.

Si Stripe esta configurado (STRIPE_SECRET_KEY + STRIPE_PRICE_ID_PRO),
genera una URL de checkout real. Si no, muestra mensaje "Proximamente".
"""
import streamlit as st
import pandas as pd

# Importar stripe_client con try/except (las keys pueden no estar configuradas)
try:
    from src.billing.stripe_client import create_checkout_session, is_configured as _stripe_configured
except Exception:
    create_checkout_session = None  # type: ignore[assignment]
    _stripe_configured = lambda: False  # noqa: E731


def _get_checkout_url(plan: str = "pro") -> str:
    """Genera URL de Stripe Checkout para el usuario actual.

    Retorna la URL o cadena vacia si Stripe no esta configurado.
    """
    if create_checkout_session is None or not _stripe_configured():
        return ""

    user = st.session_state.get("user", {})
    email = user.get("email", "")
    user_id = user.get("id", "")
    if not email:
        return ""

    try:
        return create_checkout_session(user_email=email, plan=plan, user_id=user_id) or ""
    except Exception:
        return ""


def check_feature_access(feature: str) -> bool:
    """Verifica si el usuario tiene acceso a una feature.

    Args:
        feature: 'token_lookup', 'shap_analysis', 'telegram_alerts', 'api_access'

    Returns:
        True si tiene acceso, False si no.
    """
    role = st.session_state.get("role", "free")
    if role == "admin":
        return True  # Admin tiene acceso total

    plan = st.session_state.get("profile", {}).get("subscription_plan", "free")

    from src.billing.subscription import get_plan_limits
    limits = get_plan_limits(plan)
    return limits.get(feature, False)


def show_upgrade_prompt(feature_name: str = "esta funcion"):
    """Muestra prompt de upgrade cuando el usuario no tiene acceso.

    Si Stripe esta configurado, genera una URL de checkout real.
    Si no, muestra un mensaje de "Proximamente".
    Estilo premium coherente con la paleta terminal.
    """
    st.markdown(
        f"<div style='text-align: center; padding: 40px 20px;'>"
        f"<div style='font-size: 2rem; margin-bottom: 8px;'>:lock:</div>"
        f"<h3 style='margin: 0;'>{feature_name} requiere suscripcion "
        f"<span style='color: #00ff41;'>Pro</span></h3>"
        f"</div>",
        unsafe_allow_html=True,
    )

    col1, col2 = st.columns(2)
    with col1:
        st.markdown(
            "<div style='background: #111111; border: 1px solid rgba(0,255,65,0.2); "
            "border-radius: 12px; padding: 20px;'>"
            "<h4 style='color: #00ff41; margin-top: 0;'>Pro -- $29/mes</h4>"
            "<ul style='list-style: none; padding: 0; margin: 0;'>"
            "<li style='padding: 4px 0;'><span style='color: #00ff41;'>&#10003;</span> Todas las senales diarias</li>"
            "<li style='padding: 4px 0;'><span style='color: #00ff41;'>&#10003;</span> Busqueda de tokens ilimitada</li>"
            "<li style='padding: 4px 0;'><span style='color: #00ff41;'>&#10003;</span> Analisis SHAP</li>"
            "<li style='padding: 4px 0;'><span style='color: #00ff41;'>&#10003;</span> Alertas Telegram</li>"
            "<li style='padding: 4px 0;'><span style='color: #00ff41;'>&#10003;</span> Watchlist de 10 tokens</li>"
            "</ul></div>",
            unsafe_allow_html=True,
        )
    with col2:
        st.markdown(
            "<div style='background: #111111; border: 1px solid rgba(255,255,255,0.06); "
            "border-radius: 12px; padding: 20px;'>"
            "<h4 style='color: #fbbf24; margin-top: 0;'>Enterprise -- $99/mes</h4>"
            "<ul style='list-style: none; padding: 0; margin: 0;'>"
            "<li style='padding: 4px 0;'><span style='color: #fbbf24;'>&#10003;</span> Todo lo de Pro</li>"
            "<li style='padding: 4px 0;'><span style='color: #fbbf24;'>&#10003;</span> API access</li>"
            "<li style='padding: 4px 0;'><span style='color: #fbbf24;'>&#10003;</span> Watchlist ilimitada</li>"
            "<li style='padding: 4px 0;'><span style='color: #fbbf24;'>&#10003;</span> Soporte prioritario</li>"
            "</ul></div>",
            unsafe_allow_html=True,
        )

    st.markdown("")
    # Intentar obtener URL real de Stripe Checkout
    checkout_url = _get_checkout_url("pro")

    if checkout_url:
        st.link_button("Suscribirse a Pro", checkout_url, type="primary")
    else:
        # Stripe no configurado — mostrar mensaje informativo
        st.info(
            "Pagos proximamente. Estamos configurando el sistema de "
            "suscripciones. Contacta info@memedetector.es para mas informacion."
        )


def limit_signals(df, plan: str = "free"):
    """Limita el número de señales visibles segun plan.

    Para usuarios Free, devuelve solo las señales permitidas.
    El mensaje teaser con las señales ocultas se muestra aparte
    via render_blurred_signals_teaser().
    """
    from src.billing.subscription import get_plan_limits
    limits = get_plan_limits(plan)
    max_visible = limits.get("max_signals_visible", 3)

    if len(df) > max_visible:
        return df.head(max_visible)
    return df


def get_total_signals_count() -> int:
    """Obtiene el total de señales disponibles hoy (sin limite de plan).

    Usado para mostrar al usuario Free cuantas señales se esta perdiendo.
    """
    try:
        from src.data.supabase_storage import get_storage
        storage = get_storage()
        df = storage.get_scores(min_probability=0.0, scored_today=True)
        if df.empty:
            df = storage.get_scores(min_probability=0.0)
            if not df.empty:
                df = df.head(200)
        return len(df)
    except Exception:
        return 0


def render_blurred_signals_teaser(df_all, visible_count: int):
    """Muestra filas de señales 'ocultas' con datos difuminados para Free users.

    Args:
        df_all: DataFrame completo de señales (todas, no solo las visibles).
        visible_count: Cuantas señales ya se mostraron con datos completos.
    """
    total = len(df_all)
    if total <= visible_count:
        return

    remaining = total - visible_count

    st.markdown("---")
    st.markdown(
        f":lock: **Mostrando {visible_count} de {total} señales.** "
        f"Actualiza a **Pro** para desbloquear las **{remaining} señales restantes**."
    )

    # Mostrar filas ocultas con datos difuminados (maximo 10 filas teaser)
    df_hidden = df_all.iloc[visible_count:visible_count + 10].copy()

    if df_hidden.empty:
        return

    # Preparar datos difuminados — solo se ve el nivel de señal
    blurred_rows = []
    for _, row in df_hidden.iterrows():
        signal = row.get("signal", "NONE")
        chain = row.get("chain", "")
        chain_label = chain.capitalize() if chain else "?"
        blurred_rows.append({
            "Token": "--------",
            "Chain": chain_label,
            "Score": "---",
            "Senal": signal,
            "DexScreener": "",
        })

    df_blurred = pd.DataFrame(blurred_rows)

    # Estilo CSS para difuminar las filas
    st.markdown(
        """
        <style>
        .blurred-table {
            opacity: 0.45;
            filter: blur(2px);
            pointer-events: none;
            user-select: none;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown('<div class="blurred-table" aria-hidden="true">', unsafe_allow_html=True)
    st.dataframe(
        df_blurred,
        use_container_width=True,
        hide_index=True,
        height=min(len(df_blurred) * 38 + 40, 420),
    )
    st.markdown('</div>', unsafe_allow_html=True)

    if remaining > 10:
        st.caption(f"... y {remaining - 10} señales mas.")

    # CTA de upgrade
    checkout_url = _get_checkout_url("pro")
    if checkout_url:
        st.link_button(":rocket: Desbloquear todas las señales — Pro $29/mes", checkout_url, type="primary")
    else:
        st.markdown(":rocket: **[Ver planes y precios](/pricing)**")
