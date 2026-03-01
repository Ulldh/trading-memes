"""
twitter_client.py - Cliente para la API de X (Twitter) v2.

Permite buscar menciones de tokens en X para analizar sentimiento
y actividad social. Requiere Bearer Token (tier Basic o superior).

Endpoints usados:
- GET /2/tweets/search/recent — Busqueda de tweets recientes (7 dias)

Rate limits (Basic tier):
- 450 requests / 15 min para search/recent (App-only auth)

Uso:
    from src.api.twitter_client import TwitterClient

    client = TwitterClient()

    # Buscar menciones de un token
    tweets = client.search_token_mentions("BONK", max_results=100)

    # Buscar con query personalizado
    tweets = client.search_recent("$PEPE memecoin", max_results=50)
"""

from typing import Optional

from src.api.base_client import BaseAPIClient
from src.utils.logger import get_logger
from src.utils.helpers import safe_int, safe_float

# Importar configuracion de forma segura
try:
    from config import API_URLS, RATE_LIMITS, X_BEARER_TOKEN
except ImportError:
    API_URLS = {"twitter": "https://api.twitter.com/2"}
    RATE_LIMITS = {"twitter": 30}
    X_BEARER_TOKEN = ""

logger = get_logger(__name__)


class TwitterClient(BaseAPIClient):
    """
    Cliente para la API de X (Twitter) v2.

    Hereda de BaseAPIClient para rate limiting, cache y retries.
    Requiere un Bearer Token configurado en .env como X_BEARER_TOKEN.

    Ejemplo:
        >>> client = TwitterClient()
        >>> if client.is_configured:
        ...     tweets = client.search_token_mentions("BONK")
    """

    def __init__(self):
        super().__init__(
            base_url=API_URLS.get("twitter", "https://api.twitter.com/2"),
            name="twitter",
            calls_per_minute=RATE_LIMITS.get("twitter", 30),
            cache_ttl_hours=1,  # Cache corto: datos sociales cambian rapido
        )

        # Configurar autenticacion con Bearer Token
        self.bearer_token = X_BEARER_TOKEN
        if self.bearer_token:
            self.session.headers.update({
                "Authorization": f"Bearer {self.bearer_token}",
            })

        self.is_configured = bool(self.bearer_token)

        if not self.is_configured:
            logger.warning(
                "TwitterClient: X_BEARER_TOKEN no configurado. "
                "Las features de sentimiento no estaran disponibles."
            )
        else:
            logger.info("TwitterClient inicializado con Bearer Token")

    # ================================================================
    # ENDPOINTS
    # ================================================================

    def search_recent(
        self,
        query: str,
        max_results: int = 100,
    ) -> Optional[dict]:
        """
        Busca tweets recientes (ultimos 7 dias) con la query dada.

        Args:
            query: Query de busqueda (soporta operadores de X API v2).
                   Ej: '"$BONK" -is:retweet lang:en'
            max_results: Cantidad maxima de tweets (10-100).

        Returns:
            Dict con 'data' (lista de tweets), 'includes' (autores),
            y 'meta' (conteos). None si hay error.
        """
        if not self.is_configured:
            return None

        max_results = max(10, min(100, max_results))

        params = {
            "query": query,
            "max_results": max_results,
            # Campos del tweet que necesitamos
            "tweet.fields": "created_at,public_metrics,author_id,lang",
            # Expandir informacion del autor
            "expansions": "author_id",
            "user.fields": "public_metrics,verified",
        }

        return self._get("/tweets/search/recent", params=params)

    def search_token_mentions(
        self,
        symbol: str,
        name: str = "",
        max_results: int = 100,
    ) -> Optional[dict]:
        """
        Busca menciones de un token especifico en X.

        Construye una query optimizada usando el simbolo del token
        con $ (cashtag) y el nombre, excluyendo retweets para
        evitar duplicados.

        Args:
            symbol: Simbolo del token (ej: "BONK", "PEPE").
            name: Nombre completo del token (opcional, mejora precision).
            max_results: Cantidad maxima de tweets (10-100).

        Returns:
            Dict con resultados de la busqueda, o None.
        """
        if not self.is_configured:
            return None

        if not symbol:
            return None

        # Construir query: cashtag + nombre, excluir retweets
        # Formato: ("$BONK" OR "BONK memecoin") -is:retweet
        parts = [f'"${symbol.upper()}"']
        if name and name.lower() != symbol.lower():
            parts.append(f'"{name} memecoin"')

        query = f"({' OR '.join(parts)}) -is:retweet"

        logger.info(f"Buscando menciones en X: {query}")
        return self.search_recent(query, max_results=max_results)

    def get_mention_count(self, symbol: str, name: str = "") -> dict:
        """
        Obtiene un resumen de menciones de un token.

        Devuelve metricas agregadas sin necesidad de procesar
        cada tweet individualmente.

        Args:
            symbol: Simbolo del token.
            name: Nombre del token (opcional).

        Returns:
            Dict con: total_tweets, unique_authors, total_likes,
            total_retweets, total_replies, avg_engagement.
        """
        result = {
            "total_tweets": 0,
            "unique_authors": 0,
            "total_likes": 0,
            "total_retweets": 0,
            "total_replies": 0,
            "avg_engagement": 0.0,
        }

        response = self.search_token_mentions(symbol, name)
        if not response:
            return result

        tweets = response.get("data", [])
        if not tweets:
            return result

        # Contar autores unicos
        author_ids = set()
        total_likes = 0
        total_retweets = 0
        total_replies = 0

        for tweet in tweets:
            author_ids.add(tweet.get("author_id", ""))
            metrics = tweet.get("public_metrics", {})
            total_likes += safe_int(metrics.get("like_count"))
            total_retweets += safe_int(metrics.get("retweet_count"))
            total_replies += safe_int(metrics.get("reply_count"))

        total_tweets = len(tweets)
        total_engagement = total_likes + total_retweets + total_replies

        result["total_tweets"] = total_tweets
        result["unique_authors"] = len(author_ids)
        result["total_likes"] = total_likes
        result["total_retweets"] = total_retweets
        result["total_replies"] = total_replies
        result["avg_engagement"] = (
            total_engagement / total_tweets if total_tweets > 0 else 0.0
        )

        logger.info(
            f"Menciones de {symbol}: {total_tweets} tweets, "
            f"{len(author_ids)} autores, engagement={total_engagement}"
        )
        return result
