"""
analysis/sentiment.py
──────────────────────────────────────────────────────────────────
Analyse de sentiment des articles.
- Primaire : Hugging Face Inference API (modèle multilingue)
- Fallback : Analyse par dictionnaire de mots-clés pondérés
"""

import logging
from sources.news_fetcher import NewsArticle

logger = logging.getLogger(__name__)

# ── Tentative import HuggingFace ─────────────────────────────────
_HF_AVAILABLE = False
_hf_classifier = None

try:
    from app_config.settings import HF_TOKEN
    if HF_TOKEN:
        import requests as _hf_requests
        _HF_AVAILABLE = True
        logger.info("Hugging Face Inference API activée")
except ImportError:
    pass


# ── Dictionnaire de sentiment FR (fallback) ──────────────────────

_POSITIVE_WORDS = {
    # Mots fortement positifs (poids 2)
    "hausse": 2, "croissance": 2, "bénéfice": 2, "profit": 2,
    "record": 2, "bond": 2, "envolée": 2, "surperformance": 2,
    "acquisition": 1.5, "dividende": 1.5, "relèvement": 1.5,
    # Mots modérément positifs (poids 1)
    "amélioration": 1, "optimisme": 1, "confiance": 1, "rebond": 1,
    "progression": 1, "accélération": 1, "reprise": 1, "favorable": 1,
    "soutien": 1, "investissement": 0.8, "innovation": 0.8,
    "commande": 0.8, "contrat": 0.8, "partenariat": 0.8,
    "positif": 1, "excédent": 1, "expansion": 1, "succès": 1.5,
    "upgrade": 1.5, "surpondérer": 1.5, "achat": 1,
}

_NEGATIVE_WORDS = {
    # Mots fortement négatifs (poids 2)
    "baisse": 2, "chute": 2, "effondrement": 2, "crise": 2,
    "perte": 2, "déficit": 2, "faillite": 2.5, "liquidation": 2.5,
    "récession": 2, "krach": 2.5, "plongeon": 2,
    # Mots modérément négatifs (poids 1)
    "ralentissement": 1, "inquiétude": 1, "tension": 1, "risque": 0.8,
    "sanction": 1.5, "amende": 1.5, "restructuration": 1, "licenciement": 1.5,
    "grève": 1, "pression": 0.8, "incertitude": 0.8, "dette": 0.8,
    "dégradation": 1.5, "avertissement": 1.5, "profit warning": 2,
    "négatif": 1, "sous-pondérer": 1.5, "vente": 0.5, "inflation": 0.8,
    "recul": 1, "stagnation": 0.8, "correction": 1,
}


def _keyword_sentiment(text: str) -> tuple[float, str]:
    """
    Calcule un score de sentiment par comptage pondéré de mots-clés.
    Retourne (score, label) avec score ∈ [-1, 1].
    """
    text_lower = text.lower()
    pos_score = sum(w for word, w in _POSITIVE_WORDS.items() if word in text_lower)
    neg_score = sum(w for word, w in _NEGATIVE_WORDS.items() if word in text_lower)

    total = pos_score + neg_score
    if total == 0:
        return 0.0, "neutre"

    # Normalisation entre -1 et 1
    raw = (pos_score - neg_score) / total
    score = max(-1.0, min(1.0, raw))

    if score > 0.15:
        label = "positif"
    elif score < -0.15:
        label = "négatif"
    else:
        label = "neutre"

    return round(score, 3), label


def _hf_sentiment(text: str) -> tuple[float, str]:
    """
    Appelle l'API Hugging Face Inference pour le sentiment.
    Utilise un modèle multilingue (nlptown/bert-base-multilingual-uncased-sentiment).
    """
    from app_config.settings import HF_TOKEN

    API_URL = "https://api-inference.huggingface.co/models/nlptown/bert-base-multilingual-uncased-sentiment"
    headers = {"Authorization": f"Bearer {HF_TOKEN}"}

    try:
        resp = _hf_requests.post(
            API_URL,
            headers=headers,
            json={"inputs": text[:512]},  # Limiter la longueur
            timeout=10,
        )
        if resp.status_code != 200:
            logger.warning("HF API status %d – fallback keywords", resp.status_code)
            return _keyword_sentiment(text)

        results = resp.json()
        if not results or not isinstance(results, list):
            return _keyword_sentiment(text)

        # Le modèle retourne des labels "1 star" à "5 stars"
        scores = results[0] if isinstance(results[0], list) else results
        best = max(scores, key=lambda x: x["score"])
        stars = int(best["label"].split()[0])

        # Convertir 1-5 étoiles en score [-1, 1]
        score = (stars - 3) / 2.0
        if score > 0.15:
            label = "positif"
        elif score < -0.15:
            label = "négatif"
        else:
            label = "neutre"

        return round(score, 3), label

    except Exception as exc:
        logger.warning("HF erreur : %s – fallback keywords", exc)
        return _keyword_sentiment(text)


# ── Point d'entrée ───────────────────────────────────────────────

def analyze_sentiment(articles: list[NewsArticle]) -> list[NewsArticle]:
    """
    Enrichit chaque article avec un score et un label de sentiment.
    Utilise HF si disponible, sinon fallback dictionnaire.
    """
    method = "Hugging Face" if _HF_AVAILABLE else "dictionnaire"
    logger.info("Analyse de sentiment via %s pour %d articles", method, len(articles))

    for article in articles:
        text = article.text_blob

        if _HF_AVAILABLE:
            score, label = _hf_sentiment(text)
        else:
            score, label = _keyword_sentiment(text)

        article.sentiment_score = score
        article.sentiment_label = label

    pos = sum(1 for a in articles if a.sentiment_label == "positif")
    neg = sum(1 for a in articles if a.sentiment_label == "négatif")
    neu = sum(1 for a in articles if a.sentiment_label == "neutre")
    logger.info("Sentiment : %d positif / %d négatif / %d neutre", pos, neg, neu)

    return articles
