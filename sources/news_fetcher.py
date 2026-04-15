"""
sources/news_fetcher.py
──────────────────────────────────────────────────────────────────
Récupère les actualités françaises business/économie du jour
via NewsAPI.org (primaire) ou GNews.io (fallback).
"""

import logging
from datetime import datetime, timedelta
from dataclasses import dataclass, field

import requests

from app_config.settings import NEWSAPI_KEY, GNEWS_KEY, NEWS_MAX_ARTICLES

logger = logging.getLogger(__name__)


# ── Modèle de données ────────────────────────────────────────────

@dataclass
class NewsArticle:
    """Représente un article d'actualité normalisé."""
    title: str
    description: str
    source: str
    url: str
    published_at: str
    # Champs enrichis par l'analyse
    sectors: list[str] = field(default_factory=list)
    sentiment_score: float = 0.0        # -1.0 → +1.0
    sentiment_label: str = "neutre"     # positif / négatif / neutre
    impacted_tickers: list[str] = field(default_factory=list)
    impact_level: str = ""              # fort / moyen / faible

    @property
    def text_blob(self) -> str:
        """Texte combiné pour l'analyse NLP."""
        return f"{self.title}. {self.description or ''}"


# ── NewsAPI.org ──────────────────────────────────────────────────

def _fetch_newsapi(max_articles: int) -> list[NewsArticle]:
    """
    Appelle l'endpoint /v2/top-headlines de NewsAPI.org.
    Plan gratuit : 100 requêtes/jour, 50 articles/requête max.
    """
    if not NEWSAPI_KEY:
        logger.warning("NEWSAPI_KEY absente – skip NewsAPI")
        return []

    url = "https://newsapi.org/v2/top-headlines"
    params = {
        "country": "fr",
        "category": "business",
        "pageSize": min(max_articles, 100),
        "apiKey": NEWSAPI_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("NewsAPI – erreur réseau : %s", exc)
        return []

    if data.get("status") != "ok":
        logger.error("NewsAPI – réponse KO : %s", data.get("message"))
        return []

    articles = []
    for art in data.get("articles", []):
        articles.append(NewsArticle(
            title=art.get("title", ""),
            description=art.get("description", "") or "",
            source=art.get("source", {}).get("name", ""),
            url=art.get("url", ""),
            published_at=art.get("publishedAt", ""),
        ))

    logger.info("NewsAPI → %d articles récupérés", len(articles))
    return articles


# ── Complément : NewsAPI /v2/everything (mots-clés business FR) ─

def _fetch_newsapi_everything(max_articles: int) -> list[NewsArticle]:
    """
    Complète avec /v2/everything pour capter plus de news business FR.
    Cherche des mots-clés économiques en français sur les dernières 24h.
    """
    if not NEWSAPI_KEY:
        return []

    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%S")
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": '("bourse" OR "CAC 40" OR "entreprise" OR "économie française" OR "BCE" OR "inflation")',
        "language": "fr",
        "from": yesterday,
        "sortBy": "publishedAt",
        "pageSize": min(max_articles, 100),
        "apiKey": NEWSAPI_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("NewsAPI everything – erreur : %s", exc)
        return []

    articles = []
    for art in data.get("articles", []):
        articles.append(NewsArticle(
            title=art.get("title", ""),
            description=art.get("description", "") or "",
            source=art.get("source", {}).get("name", ""),
            url=art.get("url", ""),
            published_at=art.get("publishedAt", ""),
        ))

    logger.info("NewsAPI everything → %d articles", len(articles))
    return articles


# ── GNews.io (source principale pour serveurs) ──────────────────

def _fetch_gnews(max_articles: int) -> list[NewsArticle]:
    """
    GNews.io – plan gratuit : 100 requêtes/jour, 10 articles/requête.
    On combine top-headlines + recherches thématiques pour maximiser
    le nombre d'articles business FR.
    """
    if not GNEWS_KEY:
        logger.warning("GNEWS_KEY absente – skip GNews")
        return []

    collected: list[NewsArticle] = []

    # 1. Top headlines business FR
    collected.extend(_gnews_call(
        "https://gnews.io/api/v4/top-headlines",
        {"category": "business", "lang": "fr", "country": "fr", "max": 10, "apikey": GNEWS_KEY},
    ))

    # 2. Recherches thématiques pour élargir la couverture
    search_queries = [
        "bourse CAC 40 entreprise",
        "économie France inflation BCE",
        "énergie transition écologique",
    ]
    for query in search_queries:
        if len(collected) >= max_articles:
            break
        collected.extend(_gnews_call(
            "https://gnews.io/api/v4/search",
            {"q": query, "lang": "fr", "country": "fr", "max": 10, "apikey": GNEWS_KEY},
        ))

    logger.info("GNews total → %d articles", len(collected))
    return collected


def _gnews_call(url: str, params: dict) -> list[NewsArticle]:
    """Appel unitaire à l'API GNews avec gestion d'erreurs détaillée."""
    try:
        resp = requests.get(url, params=params, timeout=15)
        data = resp.json()

        # GNews renvoie des erreurs dans le JSON même avec status 200
        if "errors" in data:
            err_msg = str(data["errors"])
            logger.error("GNews erreur API : %s", err_msg)
            _last_errors.append(f"GNews : {err_msg}")
            return []

        if resp.status_code != 200:
            logger.error("GNews HTTP %d : %s", resp.status_code, data)
            _last_errors.append(f"GNews HTTP {resp.status_code}")
            return []

        articles = []
        for art in data.get("articles", []):
            articles.append(NewsArticle(
                title=art.get("title", ""),
                description=art.get("description", "") or "",
                source=art.get("source", {}).get("name", ""),
                url=art.get("url", ""),
                published_at=art.get("publishedAt", ""),
            ))
        return articles

    except requests.RequestException as exc:
        logger.error("GNews – erreur réseau : %s", exc)
        _last_errors.append(f"GNews réseau : {exc}")
        return []


# ── Orchestrateur ────────────────────────────────────────────────

# Erreurs capturées pour affichage dans le dashboard
_last_errors: list[str] = []


def get_fetch_errors() -> list[str]:
    """Retourne les erreurs de la dernière récupération."""
    return _last_errors.copy()


def fetch_news(max_articles: int | None = None) -> list[NewsArticle]:
    """
    Point d'entrée principal.
    Priorité : GNews (fonctionne partout) → NewsAPI (localhost seulement en gratuit).
    Déduplique par titre (lower).
    """
    global _last_errors
    _last_errors = []

    limit = max_articles or NEWS_MAX_ARTICLES
    articles: list[NewsArticle] = []

    # 1. GNews en priorité (fonctionne depuis n'importe quel serveur)
    gnews_articles = _fetch_gnews(limit)
    articles.extend(gnews_articles)
    if not gnews_articles and GNEWS_KEY:
        _last_errors.append("GNews : aucun article retourné (quota épuisé ?)")

    # 2. Complément NewsAPI headlines
    #    ⚠️ Plan gratuit NewsAPI = localhost uniquement
    newsapi_articles = _fetch_newsapi(limit)
    articles.extend(newsapi_articles)
    if not newsapi_articles and NEWSAPI_KEY:
        _last_errors.append(
            "NewsAPI : aucun article retourné. "
            "Le plan gratuit ne fonctionne que depuis localhost (pas depuis Streamlit Cloud). "
            "Solution : utiliser uniquement GNews ou passer au plan payant NewsAPI."
        )

    # 3. Complément NewsAPI everything
    if len(articles) < limit:
        articles.extend(_fetch_newsapi_everything(limit - len(articles)))

    # Diagnostic si rien du tout
    if not articles:
        if not NEWSAPI_KEY and not GNEWS_KEY:
            _last_errors.append("Aucune clé API configurée. Ajoutez NEWSAPI_KEY ou GNEWS_KEY dans les Secrets.")
        elif not GNEWS_KEY:
            _last_errors.append("GNEWS_KEY absente. Sur Streamlit Cloud, GNews est nécessaire (NewsAPI gratuit = localhost).")
        logger.error("Aucun article récupéré ! Erreurs : %s", _last_errors)

    # Déduplication par titre normalisé
    seen: set[str] = set()
    unique: list[NewsArticle] = []
    for art in articles:
        key = art.title.strip().lower()
        if key and key not in seen:
            seen.add(key)
            unique.append(art)

    logger.info("Total articles dédupliqués : %d", len(unique))
    return unique[:limit]
