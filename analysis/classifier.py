"""
analysis/classifier.py
──────────────────────────────────────────────────────────────────
Classifie chaque article par secteur et identifie les tickers
potentiellement impactés via correspondance de mots-clés.
"""

import logging
import re

from app_config.settings import get_sector_map
from sources.news_fetcher import NewsArticle

logger = logging.getLogger(__name__)


def _normalize(text: str) -> str:
    """Minuscule + suppression accents légers pour matching."""
    return text.lower().strip()


def classify_articles(articles: list[NewsArticle]) -> list[NewsArticle]:
    """
    Pour chaque article, détermine :
      - Les secteurs concernés (via keywords)
      - Les tickers directement impactés (nom d'entreprise mentionné)
      - Le niveau d'impact estimé (fort si mention directe, moyen sinon)

    Modifie les articles in-place et les retourne.
    """
    sector_map = get_sector_map()

    # Pré-compiler les patterns par secteur
    sector_patterns: dict[str, list[re.Pattern]] = {}
    for sid, sdata in sector_map.items():
        patterns = []
        for kw in sdata["keywords"]:
            # Word boundary pour éviter les faux positifs
            patterns.append(re.compile(rf"\b{re.escape(kw.lower())}\b", re.IGNORECASE))
        sector_patterns[sid] = patterns

    # Index inverse : nom d'entreprise → (sector_id, ticker)
    company_index: list[tuple[re.Pattern, str, str]] = []
    for sid, sdata in sector_map.items():
        for stock in sdata["stocks"]:
            name = stock["name"]
            # Pattern sur le nom complet + sur des variantes courtes
            for variant in _company_variants(name):
                pat = re.compile(rf"\b{re.escape(variant)}\b", re.IGNORECASE)
                company_index.append((pat, sid, stock["ticker"]))

    # Classification
    for article in articles:
        blob = article.text_blob
        blob_lower = _normalize(blob)

        matched_sectors: set[str] = set()
        matched_tickers: set[str] = set()
        direct_mention = False

        # 1. Recherche de mentions directes d'entreprises
        for pat, sid, ticker in company_index:
            if pat.search(blob):
                matched_sectors.add(sid)
                matched_tickers.add(ticker)
                direct_mention = True

        # 2. Recherche par mots-clés sectoriels
        for sid, patterns in sector_patterns.items():
            for pat in patterns:
                if pat.search(blob_lower):
                    matched_sectors.add(sid)
                    # Ajouter les tickers principaux du secteur (top 3)
                    for stock in sector_map[sid]["stocks"][:3]:
                        matched_tickers.add(stock["ticker"])
                    break  # Un seul keyword suffit par secteur

        # Enrichissement de l'article
        article.sectors = list(matched_sectors)
        article.impacted_tickers = list(matched_tickers)

        if direct_mention:
            article.impact_level = "fort"
        elif matched_sectors:
            article.impact_level = "moyen"
        else:
            article.impact_level = "faible"
            # Fallback : assigner un secteur "général" si rien ne matche
            article.sectors = ["general"]

    classified = sum(1 for a in articles if a.sectors and a.sectors != ["general"])
    logger.info("Classification : %d/%d articles rattachés à un secteur", classified, len(articles))
    return articles


def _company_variants(name: str) -> list[str]:
    """
    Génère des variantes du nom d'entreprise pour le matching.
    Ex: 'Air France-KLM' → ['Air France-KLM', 'Air France', 'KLM']
    """
    variants = [name]

    # Scinder sur les séparateurs courants
    for sep in ["-", "/", "(", " – "]:
        if sep in name:
            parts = name.split(sep)
            for p in parts:
                clean = p.strip().rstrip(")")
                if len(clean) >= 3:
                    variants.append(clean)

    # Acronymes courants (prendre les majuscules)
    caps = "".join(c for c in name if c.isupper())
    if len(caps) >= 2:
        variants.append(caps)

    return variants
