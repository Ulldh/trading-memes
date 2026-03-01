"""
sentiment.py - Calculo de features de sentimiento social desde X (Twitter).

Analiza menciones de tokens en X para generar features que capturen
la atencion social, engagement y tendencia de la conversacion.

Features que calcula:
    - mention_count: Numero de tweets mencionando el token
    - unique_authors: Autores unicos que mencionan el token
    - engagement_score: Score ponderado de likes + retweets + replies
    - mention_per_author: Intensidad promedio de mencion por autor
    - like_to_mention_ratio: Likes promedio por mencion
    - virality_score: Retweets / total engagement (que tan viral es)

Estos features se calculan a partir de datos crudos del TwitterClient.
Si X API no esta configurado, todos los features devuelven None.
"""

from src.utils.helpers import safe_divide, safe_float


def compute_sentiment_features(mention_data: dict) -> dict:
    """
    Calcula features de sentimiento a partir de datos de menciones en X.

    Args:
        mention_data: Dict devuelto por TwitterClient.get_mention_count().
                      Keys esperadas: total_tweets, unique_authors,
                      total_likes, total_retweets, total_replies,
                      avg_engagement.

    Returns:
        Dict con features de sentimiento calculados.
        Todos los valores son None si no hay datos.

    Ejemplo:
        >>> data = {
        ...     "total_tweets": 50,
        ...     "unique_authors": 30,
        ...     "total_likes": 200,
        ...     "total_retweets": 80,
        ...     "total_replies": 40,
        ...     "avg_engagement": 6.4,
        ... }
        >>> features = compute_sentiment_features(data)
        >>> features["mention_count"]
        50
    """
    features = {
        "mention_count": None,
        "unique_authors": None,
        "engagement_score": None,
        "mention_per_author": None,
        "like_to_mention_ratio": None,
        "virality_score": None,
    }

    if not mention_data:
        return features

    total_tweets = safe_float(mention_data.get("total_tweets"), default=0)
    unique_authors = safe_float(mention_data.get("unique_authors"), default=0)
    total_likes = safe_float(mention_data.get("total_likes"), default=0)
    total_retweets = safe_float(mention_data.get("total_retweets"), default=0)
    total_replies = safe_float(mention_data.get("total_replies"), default=0)

    if total_tweets == 0:
        return features

    # --- mention_count: Total de tweets mencionando el token ---
    features["mention_count"] = int(total_tweets)

    # --- unique_authors: Autores unicos (diversidad de la conversacion) ---
    # Muchos autores = interes organico. Pocos = posible bot campaign.
    features["unique_authors"] = int(unique_authors)

    # --- engagement_score: Score ponderado de interacciones ---
    # Likes x1 + Retweets x3 + Replies x2 (retweets propagan mas, valen mas)
    engagement_raw = total_likes + (total_retweets * 3) + (total_replies * 2)
    features["engagement_score"] = round(engagement_raw, 2)

    # --- mention_per_author: Intensidad de mencion por autor ---
    # Si un autor menciona muchas veces, puede ser bot o shill.
    # Ratio cercano a 1 = cada autor menciona una vez (organico).
    features["mention_per_author"] = safe_divide(total_tweets, unique_authors)

    # --- like_to_mention_ratio: Likes promedio por mencion ---
    # Alto = contenido de calidad que genera engagement.
    # Bajo = spam o contenido irrelevante.
    features["like_to_mention_ratio"] = safe_divide(total_likes, total_tweets)

    # --- virality_score: Que tan viral es la conversacion ---
    # Retweets como proporcion del engagement total.
    # Alto = la gente comparte el contenido (potencial viral).
    total_engagement = total_likes + total_retweets + total_replies
    features["virality_score"] = safe_divide(total_retweets, total_engagement)

    return features
