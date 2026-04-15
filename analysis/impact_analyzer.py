"""
analysis/impact_analyzer.py
──────────────────────────────────────────────────────────────────
Croise les articles classifiés + sentiment avec les données de
marché pour produire les opportunités d'investissement.
"""

import logging
from dataclasses import dataclass, field

from app_config.settings import get_sector_map, IMPACT_TOP_STOCKS
from sources.news_fetcher import NewsArticle
from sources.market_data import StockQuote

logger = logging.getLogger(__name__)


@dataclass
class StockOpportunity:
    """Synthèse d'opportunité pour une valeur."""
    ticker: str
    name: str
    sector_id: str
    sector_label: str
    price: float
    change_pct: float
    volume: int
    # Agrégation des news impactantes
    news_count: int = 0
    avg_sentiment: float = 0.0
    max_impact: str = "faible"        # fort / moyen / faible
    related_headlines: list[str] = field(default_factory=list)
    # Suggestion générée
    signal: str = ""                   # haussier / baissier / neutre
    suggestion: str = ""               # Phrase de conseil
    confidence: str = ""               # haute / moyenne / basse


@dataclass
class SectorReport:
    """Rapport pour un secteur donné."""
    sector_id: str
    sector_label: str
    articles: list[NewsArticle] = field(default_factory=list)
    opportunities: list[StockOpportunity] = field(default_factory=list)
    overall_sentiment: float = 0.0


def _compute_signal(avg_sentiment: float, change_pct: float, impact: str) -> tuple[str, str, str]:
    """
    Génère un signal, une suggestion et un niveau de confiance
    à partir du sentiment moyen, de la variation et de l'impact.

    Retourne (signal, suggestion, confidence).
    """
    # Matrice de décision
    is_positive_news = avg_sentiment > 0.1
    is_negative_news = avg_sentiment < -0.1
    is_up = change_pct > 0.3
    is_down = change_pct < -0.3
    is_high_impact = impact == "fort"

    if is_positive_news and is_up and is_high_impact:
        return (
            "haussier",
            "Opportunité haussière court terme – Momentum positif confirmé par les news",
            "haute",
        )
    elif is_positive_news and is_down:
        return (
            "haussier",
            "Opportunité d'achat potentielle – News positives mais cours en repli (décalage)",
            "moyenne",
        )
    elif is_positive_news and not is_down:
        return (
            "haussier",
            "Contexte favorable – À surveiller pour point d'entrée",
            "moyenne" if is_high_impact else "basse",
        )
    elif is_negative_news and is_down and is_high_impact:
        return (
            "baissier",
            "Risque baissier significatif – Prudence, alléger ou couvrir",
            "haute",
        )
    elif is_negative_news and is_up:
        return (
            "baissier",
            "Attention : cours en hausse malgré news négatives – Risque de correction",
            "moyenne",
        )
    elif is_negative_news:
        return (
            "baissier",
            "Risque baissier à surveiller – Contexte défavorable",
            "moyenne" if is_high_impact else "basse",
        )
    else:
        return (
            "neutre",
            "Position long terme à consolider – Pas de signal directionnel clair",
            "basse",
        )


def analyze_impact(
    articles: list[NewsArticle],
    quotes: dict[str, StockQuote],
) -> list[SectorReport]:
    """
    Produit le rapport final par secteur :
    1. Regroupe les articles par secteur
    2. Agrège le sentiment par ticker
    3. Croise avec les données de marché
    4. Génère les signaux et suggestions
    """
    sector_map = get_sector_map()

    # ── 1. Regroupement par secteur ──────────────────────────────
    sector_articles: dict[str, list[NewsArticle]] = {sid: [] for sid in sector_map}
    sector_articles["general"] = []

    for article in articles:
        for sid in article.sectors:
            if sid in sector_articles:
                sector_articles[sid].append(article)

    # ── 2. Agrégation par ticker ─────────────────────────────────
    # ticker → {sentiments: [], impacts: [], headlines: []}
    ticker_agg: dict[str, dict] = {}

    for article in articles:
        for ticker in article.impacted_tickers:
            if ticker not in ticker_agg:
                ticker_agg[ticker] = {
                    "sentiments": [],
                    "impacts": [],
                    "headlines": [],
                    "sectors": set(),
                }
            ticker_agg[ticker]["sentiments"].append(article.sentiment_score)
            ticker_agg[ticker]["impacts"].append(article.impact_level)
            ticker_agg[ticker]["headlines"].append(article.title)
            for sid in article.sectors:
                ticker_agg[ticker]["sectors"].add(sid)

    # ── 3. Génération des SectorReport ───────────────────────────
    reports: list[SectorReport] = []

    for sid, sdata in sector_map.items():
        arts = sector_articles.get(sid, [])
        if not arts:
            continue

        # Sentiment global du secteur
        sentiments = [a.sentiment_score for a in arts if a.sentiment_score != 0]
        overall = sum(sentiments) / len(sentiments) if sentiments else 0.0

        report = SectorReport(
            sector_id=sid,
            sector_label=sdata["label"],
            articles=arts,
            overall_sentiment=round(overall, 3),
        )

        # Opportunities pour les tickers de ce secteur
        sector_tickers = {s["ticker"]: s["name"] for s in sdata["stocks"]}
        opps: list[StockOpportunity] = []

        for ticker, name in sector_tickers.items():
            quote = quotes.get(ticker)
            agg = ticker_agg.get(ticker, {})

            if not quote or quote.error:
                continue

            sents = agg.get("sentiments", [])
            avg_sent = sum(sents) / len(sents) if sents else 0.0
            impacts = agg.get("impacts", [])
            max_imp = "fort" if "fort" in impacts else ("moyen" if "moyen" in impacts else "faible")
            headlines = agg.get("headlines", [])

            signal, suggestion, confidence = _compute_signal(
                avg_sent, quote.change_pct, max_imp
            )

            opp = StockOpportunity(
                ticker=ticker,
                name=name,
                sector_id=sid,
                sector_label=sdata["label"],
                price=quote.price,
                change_pct=quote.change_pct,
                volume=quote.volume,
                news_count=len(sents),
                avg_sentiment=round(avg_sent, 3),
                max_impact=max_imp,
                related_headlines=headlines[:3],  # Top 3 headlines
                signal=signal,
                suggestion=suggestion,
                confidence=confidence,
            )
            opps.append(opp)

        # Trier par impact décroissant puis par abs(sentiment)
        opps.sort(
            key=lambda o: (
                {"fort": 3, "moyen": 2, "faible": 1}.get(o.max_impact, 0),
                abs(o.avg_sentiment),
                abs(o.change_pct),
            ),
            reverse=True,
        )

        report.opportunities = opps[:IMPACT_TOP_STOCKS]
        reports.append(report)

    # Trier les secteurs par activité (nb articles) décroissante
    reports.sort(key=lambda r: len(r.articles), reverse=True)

    logger.info(
        "Rapport généré : %d secteurs actifs, %d opportunités au total",
        len(reports),
        sum(len(r.opportunities) for r in reports),
    )
    return reports
