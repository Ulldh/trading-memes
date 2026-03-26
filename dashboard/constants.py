"""
constants.py - Constantes compartidas del dashboard.

Centraliza colores y configuraciones que se usan en multiples vistas
para evitar duplicacion y facilitar cambios globales.
"""

# Colores consistentes para las labels de clasificacion
LABEL_COLORS = {
    "gem": "#2ecc71",              # verde
    "moderate_success": "#3498db",  # azul
    "neutral": "#95a5a6",          # gris
    "failure": "#e74c3c",          # rojo
    "rug": "#1a1a1a",              # negro
    "sin_label": "#bdc3c7",        # gris claro
}

# Colores para las cadenas blockchain
CHAIN_COLORS = {
    "solana": "#9945FF",
    "ethereum": "#627EEA",
    "base": "#0052FF",
}

# Colores para niveles de senal del scorer
SIGNAL_COLORS = {
    "STRONG": "#2ecc71",  # Verde
    "MEDIUM": "#f39c12",  # Naranja
    "WEAK": "#3498db",    # Azul
    "NONE": "#95a5a6",    # Gris
}
