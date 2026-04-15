"""
Configuration centralisée du projet French Market Intel.
Charge les variables d'environnement (.env local) ou
Streamlit Secrets (déploiement Cloud) automatiquement.
"""

import os
import json
from pathlib import Path

# ── Chargement .env (local) — silencieux si absent ──────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass  # python-dotenv optionnel en mode Streamlit Cloud

# ── Streamlit Secrets → variables d'env (Cloud) ─────────────────
# Sur Streamlit Cloud, les secrets sont dans st.secrets.
# On les injecte dans os.environ pour que tout le code fonctionne
# de manière transparente.
try:
    import streamlit as _st
    for key, val in _st.secrets.items():
        if isinstance(val, str) and key not in os.environ:
            os.environ[key] = val
except Exception:
    pass  # Pas en contexte Streamlit ou pas de secrets

# ── Chemins ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "app_config"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Clés API ─────────────────────────────────────────────────────
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "")
GNEWS_KEY = os.getenv("GNEWS_KEY", "")           # Fallback si NewsAPI indisponible
POLYGON_KEY = os.getenv("POLYGON_KEY", "")         # Optionnel – sinon yfinance
HF_TOKEN = os.getenv("HF_TOKEN", "")               # Hugging Face (sentiment)

# ── Email ────────────────────────────────────────────────────────
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
EMAIL_TO = os.getenv("EMAIL_TO", "").split(",")     # Destinataires séparés par ,

# ── Paramètres métier ────────────────────────────────────────────
NEWS_MAX_ARTICLES = int(os.getenv("NEWS_MAX_ARTICLES", "50"))
REPORT_TOP_N_NEWS = int(os.getenv("REPORT_TOP_N_NEWS", "30"))
IMPACT_TOP_STOCKS = int(os.getenv("IMPACT_TOP_STOCKS", "8"))
SCHEDULER_HOUR = int(os.getenv("SCHEDULER_HOUR", "8"))   # Heure du rapport (0-23)
SCHEDULER_MINUTE = int(os.getenv("SCHEDULER_MINUTE", "30"))

# ── Chargement univers actions ───────────────────────────────────

def load_stock_universe() -> dict:
    """Charge le fichier stocks.json et renvoie le dictionnaire complet."""
    path = CONFIG_DIR / "stocks.json"
    if not path.exists():
        raise FileNotFoundError(f"Fichier univers introuvable : {path}")
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_all_tickers() -> list[str]:
    """Renvoie la liste dédupliquée de tous les tickers configurés."""
    universe = load_stock_universe()
    tickers = set()
    for sector in universe["sectors"].values():
        for stock in sector["stocks"]:
            tickers.add(stock["ticker"])
    return sorted(tickers)


def get_sector_map() -> dict[str, dict]:
    """
    Renvoie un dict {sector_id: {label, keywords, stocks}}
    pour itération rapide.
    """
    return load_stock_universe()["sectors"]


# ── Disclaimer légal ─────────────────────────────────────────────
DISCLAIMER = (
    "⚠️  **DISCLAIMER** — Ceci n'est pas un conseil d'investissement. "
    "Les informations fournies sont à titre purement informatif. "
    "Consultez un professionnel agréé avant toute décision financière."
)
