"""
scheduler.py
──────────────────────────────────────────────────────────────────
Planificateur pour l'exécution automatique quotidienne.
Utilise APScheduler (mode bloquant) ou schedule (léger).
"""

import logging
import signal
import sys

logger = logging.getLogger(__name__)


def run_scheduled(job_func, hour: int = 8, minute: int = 30):
    """
    Lance le planificateur qui exécute job_func chaque jour à l'heure donnée.
    Tente APScheduler en priorité, sinon fallback sur `schedule`.

    Args:
        job_func: Fonction à exécuter (sans arguments)
        hour: Heure d'exécution (0-23)
        minute: Minute d'exécution (0-59)
    """

    # Gestion propre de l'arrêt (Ctrl+C)
    def _signal_handler(sig, frame):
        logger.info("Arrêt du planificateur…")
        sys.exit(0)

    signal.signal(signal.SIGINT, _signal_handler)
    signal.signal(signal.SIGTERM, _signal_handler)

    try:
        _run_with_apscheduler(job_func, hour, minute)
    except ImportError:
        logger.info("APScheduler non installé – fallback sur 'schedule'")
        _run_with_schedule(job_func, hour, minute)


def _run_with_apscheduler(job_func, hour: int, minute: int):
    """Planificateur via APScheduler (plus robuste)."""
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler()
    trigger = CronTrigger(hour=hour, minute=minute, timezone="Europe/Paris")

    scheduler.add_job(job_func, trigger=trigger, id="daily_report", name="Rapport quotidien")

    logger.info(
        "⏰ Planificateur APScheduler actif — prochain run à %02d:%02d (Europe/Paris)",
        hour, minute,
    )
    logger.info("Appuyez sur Ctrl+C pour arrêter.\n")

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        scheduler.shutdown()
        logger.info("Planificateur arrêté proprement.")


def _run_with_schedule(job_func, hour: int, minute: int):
    """Fallback avec la bibliothèque `schedule` (plus légère)."""
    import schedule
    import time

    time_str = f"{hour:02d}:{minute:02d}"
    schedule.every().day.at(time_str).do(job_func)

    logger.info(
        "⏰ Planificateur schedule actif — prochain run à %s",
        time_str,
    )
    logger.info("Appuyez sur Ctrl+C pour arrêter.\n")

    try:
        while True:
            schedule.run_pending()
            time.sleep(30)
    except KeyboardInterrupt:
        logger.info("Planificateur arrêté proprement.")
