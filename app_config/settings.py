"""
Configuration centralisée du projet French Market Intel.
Charge les secrets depuis (par priorité) :
  1. Streamlit Secrets (st.secrets)  → Streamlit Cloud
  2. Variables d'environnement       → .env local / GitHub Actions
  3. Valeur par défaut               → chaîne vide
"""

import os
import json
from pathlib import Path

# ── Chargement .env (local) — silencieux si absent ──────────────
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass


def _secret(key: str, default: str = "") -> str:
    """
    Lit une clé depuis Streamlit Secrets OU os.environ.
    Streamlit Secrets est prioritaire (déploiement Cloud).
    """
    # 1. Streamlit Secrets (Cloud)
    try:
        import streamlit as _st
        val = _st.secrets.get(key)
        if val is not None and str(val).strip():
            return str(val).strip()
    except Exception:
        pass

    # 2. Variable d'environnement (.env local / CI)
    val = os.environ.get(key, "").strip()
    if val:
        return val

    return default


# ── Chemins ──────────────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "app_config"
OUTPUT_DIR = PROJECT_ROOT / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Clés API ─────────────────────────────────────────────────────
NEWSAPI_KEY = _secret("NEWSAPI_KEY")
GNEWS_KEY = _secret("GNEWS_KEY")
POLYGON_KEY = _secret("POLYGON_KEY")
HF_TOKEN = _secret("HF_TOKEN")

# ── Email ────────────────────────────────────────────────────────
SMTP_HOST = _secret("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(_secret("SMTP_PORT", "587"))
SMTP_USER = _secret("SMTP_USER")
SMTP_PASS = _secret("SMTP_PASS")
EMAIL_TO = _secret("EMAIL_TO").split(",")

# ── Paramètres métier ────────────────────────────────────────────
NEWS_MAX_ARTICLES = int(_secret("NEWS_MAX_ARTICLES", "50"))
REPORT_TOP_N_NEWS = int(_secret("REPORT_TOP_N_NEWS", "30"))
IMPACT_TOP_STOCKS = int(_secret("IMPACT_TOP_STOCKS", "8"))
SCHEDULER_HOUR = int(_secret("SCHEDULER_HOUR", "8"))
SCHEDULER_MINUTE = int(_secret("SCHEDULER_MINUTE", "30"))


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
