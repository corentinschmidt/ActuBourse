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


# ── GNews.io (fallback) ─────────────────────────────────────────

def _fetch_gnews(max_articles: int) -> list[NewsArticle]:
    """
    GNews.io – plan gratuit : 100 requêtes/jour, 10 articles/requête.
    On fait plusieurs appels pour atteindre le quota voulu.
    """
    if not GNEWS_KEY:
        logger.warning("GNEWS_KEY absente – skip GNews")
        return []

    url = "https://gnews.io/api/v4/top-headlines"
    collected: list[NewsArticle] = []
    page_size = 10  # max GNews gratuit

    params = {
        "category": "business",
        "lang": "fr",
        "country": "fr",
        "max": page_size,
        "apikey": GNEWS_KEY,
    }

    try:
        resp = requests.get(url, params=params, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        logger.error("GNews – erreur : %s", exc)
        return []

    for art in data.get("articles", []):
        collected.append(NewsArticle(
            title=art.get("title", ""),
            description=art.get("description", "") or "",
            source=art.get("source", {}).get("name", ""),
            url=art.get("url", ""),
            published_at=art.get("publishedAt", ""),
        ))

    logger.info("GNews → %d articles", len(collected))
    return collected


# ── Orchestrateur ────────────────────────────────────────────────

def fetch_news(max_articles: int | None = None) -> list[NewsArticle]:
    """
    Point d'entrée principal. Tente NewsAPI puis GNews en fallback.
    Déduplique par titre (lower).
    """
    limit = max_articles or NEWS_MAX_ARTICLES
    articles: list[NewsArticle] = []

    # 1. NewsAPI headlines
    articles.extend(_fetch_newsapi(limit))

    # 2. Complément NewsAPI everything
    remaining = limit - len(articles)
    if remaining > 0:
        articles.extend(_fetch_newsapi_everything(remaining))

    # 3. Fallback GNews si pas assez
    if len(articles) < 10:
        logger.info("Peu d'articles via NewsAPI – fallback GNews")
        articles.extend(_fetch_gnews(limit))

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
