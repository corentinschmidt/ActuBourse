"""
reporting/email_sender.py
──────────────────────────────────────────────────────────────────
Envoi automatique du rapport quotidien par email.
Supporte SMTP classique (Gmail, Outlook…) et SendGrid (optionnel).
"""

import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

from app_config.settings import SMTP_HOST, SMTP_PORT, SMTP_USER, SMTP_PASS, EMAIL_TO

logger = logging.getLogger(__name__)


def send_report_email(
    markdown_content: str,
    report_path: Path | None = None,
    recipients: list[str] | None = None,
) -> bool:
    """
    Envoie le rapport par email.

    Args:
        markdown_content: Contenu du rapport en Markdown
        report_path: Chemin vers le fichier .md (optionnel, en pièce jointe)
        recipients: Liste d'adresses email (défaut : EMAIL_TO du .env)

    Returns:
        True si envoi réussi, False sinon.
    """
    to_addrs = recipients or EMAIL_TO
    to_addrs = [a.strip() for a in to_addrs if a.strip()]

    if not to_addrs:
        logger.warning("Aucun destinataire email configuré (EMAIL_TO vide)")
        return False

    if not SMTP_USER or not SMTP_PASS:
        logger.warning("Identifiants SMTP non configurés – envoi impossible")
        return False

    # Construction du message
    date_str = datetime.now().strftime("%d/%m/%Y")
    subject = f"📊 French Market Intel — Rapport du {date_str}"

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = ", ".join(to_addrs)

    # Version texte (Markdown brut)
    text_part = MIMEText(markdown_content, "plain", "utf-8")
    msg.attach(text_part)

    # Version HTML basique (conversion Markdown → HTML)
    html_content = _markdown_to_basic_html(markdown_content)
    html_part = MIMEText(html_content, "html", "utf-8")
    msg.attach(html_part)

    # Pièce jointe .md
    if report_path and report_path.exists():
        attachment = MIMEText(report_path.read_text(encoding="utf-8"), "plain", "utf-8")
        attachment.add_header(
            "Content-Disposition", "attachment",
            filename=report_path.name,
        )
        msg.attach(attachment)

    # Envoi SMTP
    try:
        logger.info("Connexion SMTP à %s:%d…", SMTP_HOST, SMTP_PORT)
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.ehlo()
            server.starttls()
            server.ehlo()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(SMTP_USER, to_addrs, msg.as_string())

        logger.info("Email envoyé avec succès à %s", ", ".join(to_addrs))
        return True

    except smtplib.SMTPAuthenticationError:
        logger.error(
            "Échec d'authentification SMTP. Pour Gmail, utiliser un "
            "'App Password' (pas le mot de passe principal)."
        )
        return False

    except Exception as exc:
        logger.error("Erreur d'envoi email : %s", exc)
        return False


def _markdown_to_basic_html(md: str) -> str:
    """
    Conversion Markdown → HTML ultra-basique pour l'email.
    Pas de dépendance externe – juste un rendu lisible.
    """
    import re

    html_lines = [
        "<!DOCTYPE html><html><head><meta charset='utf-8'>",
        "<style>",
        "body{font-family:Arial,sans-serif;max-width:800px;margin:auto;padding:20px;color:#333}",
        "h1{color:#1a5276;border-bottom:3px solid #1a5276;padding-bottom:10px}",
        "h2{color:#2e86c1;margin-top:30px}",
        "h3{color:#2874a6}",
        "table{border-collapse:collapse;width:100%;margin:15px 0}",
        "th,td{border:1px solid #ddd;padding:8px;text-align:left;font-size:13px}",
        "th{background:#2e86c1;color:white}",
        "tr:nth-child(even){background:#f2f2f2}",
        "blockquote{border-left:4px solid #3498db;margin:10px 0;padding:5px 15px;color:#555;background:#f8f9fa}",
        "code{background:#f0f0f0;padding:2px 6px;border-radius:3px}",
        ".disclaimer{background:#fff3cd;border:1px solid #ffc107;padding:15px;border-radius:5px;margin:20px 0}",
        "</style></head><body>",
    ]

    for line in md.split("\n"):
        stripped = line.strip()

        if stripped.startswith("### "):
            html_lines.append(f"<h3>{stripped[4:]}</h3>")
        elif stripped.startswith("## "):
            html_lines.append(f"<h2>{stripped[3:]}</h2>")
        elif stripped.startswith("# "):
            html_lines.append(f"<h1>{stripped[2:]}</h1>")
        elif stripped.startswith("|"):
            # Ligne de tableau
            if set(stripped.replace("|", "").strip()) <= {"-", " ", ":"}:
                continue  # Séparateur
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            tag = "th" if not hasattr(_markdown_to_basic_html, "_in_table") else "td"
            _markdown_to_basic_html._in_table = True
            row = "".join(f"<{tag}>{c}</{tag}>" for c in cells)
            html_lines.append(f"<tr>{row}</tr>")
        elif stripped.startswith("> "):
            html_lines.append(f"<blockquote>{stripped[2:]}</blockquote>")
        elif stripped.startswith("- "):
            html_lines.append(f"<li>{stripped[2:]}</li>")
        elif stripped == "---":
            html_lines.append("<hr>")
            _markdown_to_basic_html._in_table = False
        elif stripped.startswith("⚠️"):
            html_lines.append(f"<div class='disclaimer'>{stripped}</div>")
        elif stripped:
            # Bold **text**
            processed = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", stripped)
            processed = re.sub(r"\*(.+?)\*", r"<em>\1</em>", processed)
            html_lines.append(f"<p>{processed}</p>")

    html_lines.append("</body></html>")
    return "\n".join(html_lines)
