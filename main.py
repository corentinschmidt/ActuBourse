#!/usr/bin/env python3
"""
main.py — French Market Intel
══════════════════════════════════════════════════════════════════
Outil professionnel d'analyse quotidienne des marchés français.
Récupère les actualités, analyse le sentiment, croise avec les
données boursières et génère un rapport d'opportunités.

Usage:
    python main.py                  # Exécution unique (console + fichier)
    python main.py --email          # Exécution unique + envoi email
    python main.py --schedule       # Mode planifié (quotidien)
    python main.py --schedule --email  # Planifié + email
    python main.py --verbose        # Mode debug

Auteur : French Market Intel v1.0
"""

import argparse
import logging
import sys
from datetime import datetime

# ── Configuration du logging ─────────────────────────────────────

def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    fmt = "%(asctime)s │ %(levelname)-8s │ %(name)-25s │ %(message)s"
    logging.basicConfig(level=level, format=fmt, datefmt="%H:%M:%S")
    # Réduire le bruit des libs externes
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("yfinance").setLevel(logging.WARNING)
    logging.getLogger("apscheduler").setLevel(logging.WARNING)


logger = logging.getLogger("main")


# ── Pipeline principal ───────────────────────────────────────────

def run_pipeline(send_email: bool = False) -> None:
    """
    Exécute le pipeline complet d'analyse :
    1. Récupération des news
    2. Classification par secteur
    3. Analyse de sentiment
    4. Récupération des cours boursiers
    5. Analyse d'impact et génération d'opportunités
    6. Génération du rapport (console + Markdown + email)
    """
    from sources.news_fetcher import fetch_news
    from sources.market_data import fetch_quotes
    from analysis.classifier import classify_articles
    from analysis.sentiment import analyze_sentiment
    from analysis.impact_analyzer import analyze_impact
    from reporting.markdown_report import (
        generate_markdown, save_report, print_console_report,
    )
    from reporting.email_sender import send_report_email
    from config.settings import get_all_tickers

    start = datetime.now()
    logger.info("=" * 60)
    logger.info("🚀 FRENCH MARKET INTEL — Démarrage du pipeline")
    logger.info("=" * 60)

    # ── Étape 1 : Récupération des news ──────────────────────────
    logger.info("📰 Étape 1/6 — Récupération des actualités…")
    articles = fetch_news()
    if not articles:
        logger.error("Aucun article récupéré. Vérifiez vos clés API (NEWSAPI_KEY / GNEWS_KEY).")
        logger.error("Le rapport sera vide. Arrêt du pipeline.")
        return
    logger.info("   → %d articles récupérés", len(articles))

    # ── Étape 2 : Classification par secteur ─────────────────────
    logger.info("🏷️  Étape 2/6 — Classification sectorielle…")
    articles = classify_articles(articles)
    sectors_found = set()
    for a in articles:
        sectors_found.update(a.sectors)
    logger.info("   → %d secteurs identifiés", len(sectors_found))

    # ── Étape 3 : Analyse de sentiment ───────────────────────────
    logger.info("🧠 Étape 3/6 — Analyse de sentiment…")
    articles = analyze_sentiment(articles)

    # ── Étape 4 : Données boursières ─────────────────────────────
    logger.info("📈 Étape 4/6 — Récupération des cours boursiers…")
    tickers = get_all_tickers()
    quotes = fetch_quotes(tickers)
    ok = sum(1 for q in quotes.values() if not q.error)
    logger.info("   → %d/%d cours récupérés avec succès", ok, len(tickers))

    # ── Étape 5 : Analyse d'impact ───────────────────────────────
    logger.info("🎯 Étape 5/6 — Analyse d'impact et opportunités…")
    reports = analyze_impact(articles, quotes)
    total_opps = sum(len(r.opportunities) for r in reports)
    logger.info("   → %d secteurs actifs, %d opportunités", len(reports), total_opps)

    # ── Étape 6 : Génération du rapport ──────────────────────────
    logger.info("📝 Étape 6/6 — Génération du rapport…")

    # Console
    print_console_report(reports)

    # Markdown
    md_content = generate_markdown(reports)
    report_path = save_report(md_content)
    logger.info("   → Rapport Markdown : %s", report_path)

    # Email (optionnel)
    if send_email:
        logger.info("📧 Envoi du rapport par email…")
        success = send_report_email(md_content, report_path)
        if success:
            logger.info("   → Email envoyé avec succès ✓")
        else:
            logger.warning("   → Échec de l'envoi email ✗")

    # Bilan
    elapsed = (datetime.now() - start).total_seconds()
    logger.info("─" * 60)
    logger.info("✅ Pipeline terminé en %.1f secondes", elapsed)
    logger.info("─" * 60)


# ── Point d'entrée CLI ───────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="French Market Intel — Analyse quotidienne des marchés français",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemples :
  python main.py                    Exécution unique (console + fichier)
  python main.py --email            Exécution + envoi email
  python main.py --schedule         Mode planifié quotidien
  python main.py --schedule --email Mode planifié + email
  python main.py --verbose          Mode debug détaillé
        """,
    )

    parser.add_argument(
        "--email", action="store_true",
        help="Envoyer le rapport par email après génération",
    )
    parser.add_argument(
        "--schedule", action="store_true",
        help="Mode planifié : exécution quotidienne automatique",
    )
    parser.add_argument(
        "--hour", type=int, default=None,
        help="Heure d'exécution en mode planifié (0-23, défaut: .env SCHEDULER_HOUR)",
    )
    parser.add_argument(
        "--minute", type=int, default=None,
        help="Minute d'exécution (0-59, défaut: .env SCHEDULER_MINUTE)",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Activer les logs de debug",
    )

    args = parser.parse_args()
    setup_logging(verbose=args.verbose)

    if args.schedule:
        # Mode planifié
        from config.settings import SCHEDULER_HOUR, SCHEDULER_MINUTE
        hour = args.hour if args.hour is not None else SCHEDULER_HOUR
        minute = args.minute if args.minute is not None else SCHEDULER_MINUTE

        from scheduler import run_scheduled
        logger.info("Mode planifié activé — rapport quotidien à %02d:%02d", hour, minute)

        # Exécuter une première fois immédiatement
        logger.info("Première exécution immédiate…")
        run_pipeline(send_email=args.email)

        # Puis planifier
        run_scheduled(
            job_func=lambda: run_pipeline(send_email=args.email),
            hour=hour,
            minute=minute,
        )
    else:
        # Exécution unique
        run_pipeline(send_email=args.email)


if __name__ == "__main__":
    main()
