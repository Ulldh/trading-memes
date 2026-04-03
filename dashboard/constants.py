"""
constants.py - Constantes compartidas del dashboard.

Centraliza colores y configuraciones que se usan en multiples vistas
para evitar duplicacion y facilitar cambios globales.

Paleta coherente con la landing page (terminal/hacker aesthetic):
  - Fondo: #0a0a0a (gestionado por config.toml)
  - Acento primario: #00ff41 (verde terminal)
  - Gem/oro: #fbbf24
  - Peligro: #ef4444
"""

# Colores consistentes para las labels de clasificacion
LABEL_COLORS = {
    "gem": "#00ff41",              # verde terminal
    "moderate_success": "#3b82f6",  # azul
    "neutral": "#6b7280",          # gris
    "failure": "#ef4444",          # rojo
    "rug": "#1a1a1a",              # negro
    "sin_label": "#4b5563",        # gris oscuro
}

# Colores para las cadenas blockchain
CHAIN_COLORS = {
    "solana": "#9945FF",
    "ethereum": "#627EEA",
    "base": "#0052FF",
}

# Colores para niveles de senal del scorer
SIGNAL_COLORS = {
    "STRONG": "#00ff41",  # Verde terminal (acento primario)
    "MEDIUM": "#fbbf24",  # Oro/amarillo
    "WEAK": "#6b7280",    # Gris
    "NONE": "#374151",    # Gris oscuro
}

# Badge colors para roles de usuario
ROLE_COLORS = {
    "admin": "#ef4444",
    "pro": "#00ff41",
    "free": "#6b7280",
}
