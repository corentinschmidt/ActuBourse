"""
sources/market_data.py
──────────────────────────────────────────────────────────────────
Récupère les données boursières en temps réel pour les valeurs
françaises (.PA) via yfinance (primaire) ou Polygon.io (fallback).
"""

import logging
from dataclasses import dataclass

import yfinance as yf
import requests

from app_config.settings import POLYGON_KEY, get_all_tickers

logger = logging.getLogger(__name__)


@dataclass
class StockQuote:
    """Snapshot d'une valeur à un instant t."""
    ticker: str
    name: str
    price: float
    change_pct: float        # Variation % du jour
    volume: int
    prev_close: float
    day_high: float
    day_low: float
    market_cap: float
    currency: str = "EUR"
    error: str = ""          # Non vide si échec de récupération


# ── yfinance (par batch) ─────────────────────────────────────────

def _fetch_yfinance(tickers: list[str]) -> dict[str, StockQuote]:
    """
    Récupère les quotes via yfinance en un seul appel batch.
    yfinance est gratuit et ne nécessite pas de clé API.
    """
    results: dict[str, StockQuote] = {}

    if not tickers:
        return results

    try:
        # Téléchargement batch – .info est lent, on utilise .download + fast_info
        batch = yf.Tickers(" ".join(tickers))

        for ticker_str in tickers:
            try:
                tkr = batch.tickers.get(ticker_str)
                if tkr is None:
                    results[ticker_str] = StockQuote(
                        ticker=ticker_str, name=ticker_str, price=0,
                        change_pct=0, volume=0, prev_close=0,
                        day_high=0, day_low=0, market_cap=0,
                        error="Ticker introuvable",
                    )
                    continue

                info = tkr.fast_info

                price = float(getattr(info, "last_price", 0) or 0)
                prev = float(getattr(info, "previous_close", 0) or 0)
                change = ((price - prev) / prev * 100) if prev else 0.0

                results[ticker_str] = StockQuote(
                    ticker=ticker_str,
                    name=getattr(info, "short_name", ticker_str) if hasattr(info, "short_name") else ticker_str,
                    price=round(price, 2),
                    change_pct=round(change, 2),
                    volume=int(getattr(info, "last_volume", 0) or 0),
                    prev_close=round(prev, 2),
                    day_high=round(float(getattr(info, "day_high", 0) or 0), 2),
                    day_low=round(float(getattr(info, "day_low", 0) or 0), 2),
                    market_cap=float(getattr(info, "market_cap", 0) or 0),
                    currency=getattr(info, "currency", "EUR") or "EUR",
                )

            except Exception as exc:
                logger.warning("yfinance erreur pour %s : %s", ticker_str, exc)
                results[ticker_str] = StockQuote(
                    ticker=ticker_str, name=ticker_str, price=0,
                    change_pct=0, volume=0, prev_close=0,
                    day_high=0, day_low=0, market_cap=0,
                    error=str(exc),
                )

    except Exception as exc:
        logger.error("yfinance batch erreur : %s", exc)

    return results


# ── Polygon.io (optionnel) ───────────────────────────────────────

def _fetch_polygon(tickers: list[str]) -> dict[str, StockQuote]:
    """
    Fallback via Polygon.io pour les tickers Euronext Paris.
    Nécessite un plan payant pour les données non-US en temps réel.
    On utilise le snapshot grouped daily pour minimiser les appels.
    """
    if not POLYGON_KEY:
        return {}

    results: dict[str, StockQuote] = {}

    for ticker_str in tickers:
        # Polygon utilise le format X:TICKEREUR pour le forex,
        # mais pour Euronext on peut requêter par ISIN ou ticker classique.
        # On essaie le /v2/aggs/ticker/ endpoint.
        polygon_ticker = ticker_str.replace(".PA", "")
        url = f"https://api.polygon.io/v2/snapshot/locale/global/markets/stocks/tickers/{polygon_ticker}"
        params = {"apiKey": POLYGON_KEY}

        try:
            resp = requests.get(url, params=params, timeout=10)
            if resp.status_code != 200:
                continue
            data = resp.json()
            snap = data.get("ticker", {})
            day = snap.get("day", {})

            price = day.get("c", 0)
            prev = snap.get("prevDay", {}).get("c", 0)
            change = ((price - prev) / prev * 100) if prev else 0

            results[ticker_str] = StockQuote(
                ticker=ticker_str,
                name=ticker_str,
                price=round(price, 2),
                change_pct=round(change, 2),
                volume=int(day.get("v", 0)),
                prev_close=round(prev, 2),
                day_high=round(day.get("h", 0), 2),
                day_low=round(day.get("l", 0), 2),
                market_cap=0,
            )
        except Exception as exc:
            logger.warning("Polygon erreur pour %s : %s", ticker_str, exc)

    return results


# ── Point d'entrée ───────────────────────────────────────────────

def fetch_quotes(tickers: list[str] | None = None) -> dict[str, StockQuote]:
    """
    Récupère les données boursières pour la liste de tickers donnée.
    Priorité : yfinance → Polygon fallback pour les manquants.
    """
    if tickers is None:
        tickers = get_all_tickers()

    logger.info("Récupération des cours pour %d tickers…", len(tickers))

    # Primaire : yfinance
    quotes = _fetch_yfinance(tickers)

    # Fallback Polygon pour les erreurs
    failed = [t for t, q in quotes.items() if q.error]
    if failed and POLYGON_KEY:
        logger.info("Fallback Polygon pour %d tickers en erreur", len(failed))
        polygon_data = _fetch_polygon(failed)
        quotes.update(polygon_data)

    ok_count = sum(1 for q in quotes.values() if not q.error)
    logger.info("Quotes OK : %d / %d", ok_count, len(tickers))
    return quotes
