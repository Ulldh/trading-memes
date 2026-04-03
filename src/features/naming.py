"""
naming.py — Features basados en el nombre y simbolo del token.

Los tokens con ciertos patrones en el nombre tienen diferentes
probabilidades de exito. Los memecoins siguen tendencias narrativas:
- Tokens con nombres de animales (pepe, doge) suelen tener comunidades
- Tokens con keywords de AI (gpt, agent) siguen la narrativa tech
- Tokens con numeros en el nombre ("PEPE2.0", "DOGE3X") suelen ser copias
- Simbolos en ALL CAPS es lo standard, pero nombres inusuales destacan

Features que calcula:
    - name_length: largo del nombre del token
    - symbol_length: largo del simbolo
    - has_meme_keyword: si contiene palabras meme populares
    - has_ai_keyword: si contiene palabras de AI/tech
    - has_animal_keyword: si contiene nombres de animales
    - is_all_caps_symbol: si el simbolo es todo mayusculas
    - has_numbers_in_name: si el nombre contiene numeros (comun en copias)
    - name_word_count: numero de palabras en el nombre

Uso:
    from src.features.naming import compute_naming_features

    features = compute_naming_features("Pepe The Frog", "PEPE")
    print(features["has_meme_keyword"])  # 1
    print(features["has_animal_keyword"])  # 1 (frog)
"""

import re


# Palabras clave de memes populares
# Estos son los nombres y conceptos mas recurrentes en memecoins exitosos
MEME_KEYWORDS = {
    "pepe", "doge", "inu", "shib", "wojak", "chad", "based",
    "moon", "elon", "trump",
}

# Palabras clave de la narrativa AI/tech
# Los tokens de AI han tenido un boom desde 2024
AI_KEYWORDS = {
    "ai", "gpt", "agent", "neural", "llm",
}

# Nombres de animales comunes en memecoins
# Los tokens con mascotas animales tienden a generar comunidad
ANIMAL_KEYWORDS = {
    "cat", "dog", "frog", "penguin", "bear", "bull", "ape", "monkey",
}


def compute_naming_features(name: str, symbol: str) -> dict:
    """
    Calcula features basados en el nombre y simbolo del token.

    Analiza patrones en el nombre y simbolo que pueden correlacionar
    con el exito o fracaso del token. Los memecoins exitosos suelen
    tener nombres cortos, memorables y asociados a narrativas populares.

    Args:
        name: Nombre completo del token (ej: "Pepe The Frog").
        symbol: Simbolo del token (ej: "PEPE").

    Returns:
        Dict plano con los features de naming.
        Todos los valores son int o float, nunca None.

    Ejemplo:
        >>> features = compute_naming_features("Pepe The Frog", "PEPE")
        >>> features["has_meme_keyword"]
        1
        >>> features["name_word_count"]
        3
        >>> features["is_all_caps_symbol"]
        1
    """
    # Normalizar inputs: string vacio si None
    name = str(name or "").strip()
    symbol = str(symbol or "").strip()

    # Convertir a minusculas para busqueda de keywords
    name_lower = name.lower()
    symbol_lower = symbol.lower()

    # Texto combinado para buscar keywords (nombre + simbolo)
    combined = f"{name_lower} {symbol_lower}"

    # --- name_length: largo del nombre ---
    # Nombres cortos son mas memorables, muy largos suelen ser scam
    name_length = len(name)

    # --- symbol_length: largo del simbolo ---
    # Simbolos standard tienen 3-5 caracteres
    symbol_length = len(symbol)

    # --- has_meme_keyword: contiene palabra meme popular ---
    # Buscar si alguna keyword meme aparece en el nombre o simbolo
    has_meme = _has_any_keyword(combined, MEME_KEYWORDS)

    # --- has_ai_keyword: contiene palabra de AI/tech ---
    has_ai = _has_any_keyword(combined, AI_KEYWORDS)

    # --- has_animal_keyword: contiene nombre de animal ---
    has_animal = _has_any_keyword(combined, ANIMAL_KEYWORDS)

    # --- is_all_caps_symbol: simbolo todo en mayusculas ---
    # La mayoria de tokens tienen simbolo en mayusculas (PEPE, DOGE)
    # Simbolos en minusculas o mixed case son inusuales
    is_all_caps = 1 if symbol and symbol == symbol.upper() and symbol.isalpha() else 0

    # --- has_numbers_in_name: nombre contiene numeros ---
    # Comun en copias/scams: "PEPE2.0", "DOGE3X", "SHIB1000"
    # Tokens originales rara vez tienen numeros en el nombre
    has_numbers = 1 if re.search(r"\d", name) else 0

    # --- name_word_count: numero de palabras en el nombre ---
    # Nombres de 1-2 palabras son mas memorables
    # Nombres muy largos ("Super Mega Ultra Doge Inu V2") son sospechosos
    words = name.split()
    word_count = len(words) if words and words[0] else 0

    return {
        "name_length": name_length,
        "symbol_length": symbol_length,
        "has_meme_keyword": has_meme,
        "has_ai_keyword": has_ai,
        "has_animal_keyword": has_animal,
        "is_all_caps_symbol": is_all_caps,
        "has_numbers_in_name": has_numbers,
        "name_word_count": word_count,
    }


def _has_any_keyword(text: str, keywords: set) -> int:
    """
    Busca si alguna keyword aparece en el texto.

    Usa busqueda de substrings para detectar keywords
    incluso cuando son parte de una palabra mas larga
    (ej: "dogefather" contiene "doge").

    Args:
        text: Texto donde buscar (ya en minusculas).
        keywords: Set de keywords a buscar.

    Returns:
        1 si encuentra alguna keyword, 0 si no.
    """
    for keyword in keywords:
        if keyword in text:
            return 1
    return 0
