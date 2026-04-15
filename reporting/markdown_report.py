"""
reporting/markdown_report.py
──────────────────────────────────────────────────────────────────
Génère le rapport quotidien en Markdown + affichage console riche.
"""

import logging
from datetime import datetime
from pathlib import Path

from app_config.settings import DISCLAIMER, OUTPUT_DIR
from analysis.impact_analyzer import SectorReport, StockOpportunity

logger = logging.getLogger(__name__)


# ── Symboles visuels ─────────────────────────────────────────────

_SIGNAL_EMOJI = {
    "haussier": "🟢",
    "baissier": "🔴",
    "neutre": "⚪",
}

_IMPACT_EMOJI = {
    "fort": "🔥",
    "moyen": "⚡",
    "faible": "💤",
}

_SENTIMENT_EMOJI = {
    "positif": "📈",
    "négatif": "📉",
    "neutre": "➡️",
}


def _format_change(pct: float) -> str:
    """Formate la variation avec signe et couleur Markdown."""
    if pct > 0:
        return f"+{pct:.2f}%"
    elif pct < 0:
        return f"{pct:.2f}%"
    return "0.00%"


def _format_volume(vol: int) -> str:
    """Formate le volume lisible."""
    if vol >= 1_000_000:
        return f"{vol / 1_000_000:.1f}M"
    elif vol >= 1_000:
        return f"{vol / 1_000:.0f}K"
    return str(vol)


def _sentiment_bar(score: float) -> str:
    """Barre visuelle ASCII du sentiment [-1, +1]."""
    normalized = int((score + 1) * 5)  # 0-10
    return "▓" * normalized + "░" * (10 - normalized)


# ── Génération Markdown ──────────────────────────────────────────

def generate_markdown(reports: list[SectorReport]) -> str:
    """
    Produit le rapport complet en Markdown structuré.
    """
    now = datetime.now()
    lines: list[str] = []

    # En-tête
    lines.append(f"# 📊 French Market Intel — Rapport du {now.strftime('%d/%m/%Y')}")
    lines.append(f"*Généré à {now.strftime('%H:%M')} (heure de Paris)*\n")
    lines.append("---\n")

    # Résumé exécutif
    total_articles = sum(len(r.articles) for r in reports)
    total_opps = sum(len(r.opportunities) for r in reports)
    bull = sum(1 for r in reports for o in r.opportunities if o.signal == "haussier")
    bear = sum(1 for r in reports for o in r.opportunities if o.signal == "baissier")

    lines.append("## 🎯 Résumé Exécutif\n")
    lines.append(f"| Métrique | Valeur |")
    lines.append(f"|----------|--------|")
    lines.append(f"| Articles analysés | **{total_articles}** |")
    lines.append(f"| Secteurs actifs | **{len(reports)}** |")
    lines.append(f"| Opportunités identifiées | **{total_opps}** |")
    lines.append(f"| Signaux haussiers 🟢 | **{bull}** |")
    lines.append(f"| Signaux baissiers 🔴 | **{bear}** |")
    lines.append("")

    # Tableau des top opportunités
    all_opps: list[StockOpportunity] = []
    for r in reports:
        all_opps.extend(r.opportunities)
    all_opps.sort(key=lambda o: abs(o.avg_sentiment), reverse=True)
    top_opps = [o for o in all_opps if o.signal != "neutre"][:10]

    if top_opps:
        lines.append("## 🏆 Top Opportunités du Jour\n")
        lines.append("| Signal | Valeur | Cours | Var. Jour | Impact | Suggestion |")
        lines.append("|--------|--------|-------|-----------|--------|------------|")
        for o in top_opps:
            sig = _SIGNAL_EMOJI.get(o.signal, "")
            imp = _IMPACT_EMOJI.get(o.max_impact, "")
            lines.append(
                f"| {sig} {o.signal.upper()} | **{o.name}** ({o.ticker}) | "
                f"{o.price:.2f}€ | {_format_change(o.change_pct)} | "
                f"{imp} {o.max_impact} | {o.suggestion} |"
            )
        lines.append("")

    # Détail par secteur
    lines.append("---\n")
    lines.append("## 📰 Détail par Secteur\n")

    for report in reports:
        sentiment_emoji = "📈" if report.overall_sentiment > 0.1 else ("📉" if report.overall_sentiment < -0.1 else "➡️")
        lines.append(f"### {sentiment_emoji} {report.sector_label}")
        lines.append(f"*Sentiment global : {report.overall_sentiment:+.2f} — {len(report.articles)} article(s)*\n")

        # Articles du secteur
        for i, art in enumerate(report.articles[:5], 1):
            sent_e = _SENTIMENT_EMOJI.get(art.sentiment_label, "")
            impact_e = _IMPACT_EMOJI.get(art.impact_level, "")
            lines.append(f"**{i}. {art.title}** {sent_e} {impact_e}")
            if art.description:
                desc = art.description[:200].rstrip()
                lines.append(f"> {desc}")
            lines.append(f"*Source : {art.source} | Sentiment : {art.sentiment_label} ({art.sentiment_score:+.2f})*\n")

        # Opportunités du secteur
        if report.opportunities:
            lines.append(f"**Valeurs impactées :**\n")
            lines.append("| Ticker | Nom | Cours | Var. % | Volume | Signal | Confiance |")
            lines.append("|--------|-----|-------|--------|--------|--------|-----------|")
            for o in report.opportunities:
                sig = _SIGNAL_EMOJI.get(o.signal, "")
                lines.append(
                    f"| {o.ticker} | {o.name} | {o.price:.2f}€ | "
                    f"{_format_change(o.change_pct)} | {_format_volume(o.volume)} | "
                    f"{sig} {o.signal} | {o.confidence} |"
                )

            lines.append("")
            # Suggestions détaillées
            for o in report.opportunities:
                if o.suggestion:
                    sig = _SIGNAL_EMOJI.get(o.signal, "")
                    lines.append(f"- {sig} **{o.name}** : {o.suggestion}")
            lines.append("")

        lines.append("---\n")

    # Disclaimer
    lines.append(f"\n{DISCLAIMER}\n")
    lines.append(f"\n*Rapport généré automatiquement par French Market Intel v1.0*")

    return "\n".join(lines)


def save_report(content: str, filename: str | None = None) -> Path:
    """Sauvegarde le rapport Markdown dans le dossier output/."""
    if filename is None:
        date_str = datetime.now().strftime("%Y-%m-%d_%H%M")
        filename = f"rapport_{date_str}.md"

    filepath = OUTPUT_DIR / filename
    filepath.write_text(content, encoding="utf-8")
    logger.info("Rapport sauvegardé : %s", filepath)
    return filepath


# ── Affichage console (rich) ─────────────────────────────────────

def print_console_report(reports: list[SectorReport]) -> None:
    """
    Affiche un résumé coloré dans le terminal via rich.
    Fallback sur print standard si rich n'est pas installé.
    """
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel
        from rich.text import Text

        console = Console()

        # Titre
        console.print(Panel.fit(
            "[bold cyan]📊 FRENCH MARKET INTEL[/] — "
            f"Rapport du {datetime.now().strftime('%d/%m/%Y %H:%M')}",
            border_style="cyan",
        ))

        # Top opportunités
        all_opps = [o for r in reports for o in r.opportunities if o.signal != "neutre"]
        all_opps.sort(key=lambda o: abs(o.avg_sentiment), reverse=True)

        if all_opps:
            table = Table(title="🏆 Top Opportunités", show_lines=True)
            table.add_column("Signal", justify="center", width=10)
            table.add_column("Valeur", width=25)
            table.add_column("Cours", justify="right", width=10)
            table.add_column("Var. %", justify="right", width=10)
            table.add_column("Impact", justify="center", width=8)
            table.add_column("Suggestion", width=50)

            for o in all_opps[:10]:
                color = "green" if o.signal == "haussier" else "red"
                var_color = "green" if o.change_pct > 0 else ("red" if o.change_pct < 0 else "white")

                table.add_row(
                    f"[bold {color}]{o.signal.upper()}[/]",
                    f"[bold]{o.name}[/]\n[dim]{o.ticker}[/]",
                    f"{o.price:.2f}€",
                    f"[{var_color}]{_format_change(o.change_pct)}[/]",
                    _IMPACT_EMOJI.get(o.max_impact, ""),
                    o.suggestion,
                )

            console.print(table)
            console.print()

        # Résumé par secteur
        for report in reports:
            color = "green" if report.overall_sentiment > 0.1 else ("red" if report.overall_sentiment < -0.1 else "yellow")
            console.print(
                f"  [{color}]●[/] [bold]{report.sector_label}[/] — "
                f"{len(report.articles)} news, sentiment: {report.overall_sentiment:+.2f}, "
                f"{len(report.opportunities)} valeurs"
            )

        console.print(f"\n[dim]{DISCLAIMER}[/]\n")

    except ImportError:
        # Fallback sans rich
        print("=" * 70)
        print(f"📊 FRENCH MARKET INTEL — {datetime.now().strftime('%d/%m/%Y %H:%M')}")
        print("=" * 70)

        for report in reports:
            print(f"\n▶ {report.sector_label} ({len(report.articles)} news)")
            for o in report.opportunities:
                print(f"  {o.signal.upper():>10} | {o.name:20s} | {o.price:>8.2f}€ | {_format_change(o.change_pct):>8} | {o.suggestion}")

        print(f"\n{DISCLAIMER}")
