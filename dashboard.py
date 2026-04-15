"""
dashboard.py — French Market Intel v2
══════════════════════════════════════════════════════════════════
Dashboard interactif Streamlit pour visualiser le rapport
d'analyse quotidienne des marchés français.

Usage:
    streamlit run dashboard.py
    streamlit run dashboard.py --server.port 8501
"""

import os
import sys
from pathlib import Path

# ══════════════════════════════════════════════════════════════════
# Résolution du chemin — compatible local + Streamlit Cloud
# ══════════════════════════════════════════════════════════════════
_THIS_DIR = Path(__file__).resolve().parent

# Chercher app_config/ : soit au même niveau que dashboard.py,
# soit dans un sous-dossier (cas où le tar.gz crée un dossier parent)
_PROJECT_ROOT = None

if (_THIS_DIR / "app_config").is_dir():
    _PROJECT_ROOT = _THIS_DIR
else:
    # Chercher dans les sous-dossiers immédiats
    for child in _THIS_DIR.iterdir():
        if child.is_dir() and (child / "app_config").is_dir():
            _PROJECT_ROOT = child
            break

if _PROJECT_ROOT is None:
    # Dernier recours : chercher l'ancien nom "config"
    if (_THIS_DIR / "config").is_dir() and (_THIS_DIR / "config" / "settings.py").exists():
        os.rename(str(_THIS_DIR / "config"), str(_THIS_DIR / "app_config"))
        _PROJECT_ROOT = _THIS_DIR

if _PROJECT_ROOT is None:
    import streamlit as st
    st.error("❌ **Erreur de structure du projet**")
    st.markdown("Le dossier `app_config/` est introuvable. Voici ce que contient le répertoire :")
    content = sorted([f"{'📁' if p.is_dir() else '📄'} {p.name}" for p in _THIS_DIR.iterdir()])
    st.code("\n".join(content))
    st.markdown("""
**Solution :** Vérifiez que votre repo GitHub contient cette structure à la racine :
```
├── dashboard.py
├── app_config/
│   ├── __init__.py
│   ├── settings.py
│   └── stocks.json
├── sources/
├── analysis/
├── reporting/
```
Si vous avez un ancien dossier `config/`, renommez-le en `app_config/`.
    """)
    st.stop()

os.chdir(_PROJECT_ROOT)
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

# ── Imports projet ───────────────────────────────────────────────
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from datetime import datetime

from app_config.settings import DISCLAIMER, get_sector_map, get_all_tickers, OUTPUT_DIR
from sources.news_fetcher import fetch_news, NewsArticle
from sources.market_data import fetch_quotes, StockQuote
from analysis.classifier import classify_articles
from analysis.sentiment import analyze_sentiment
from analysis.impact_analyzer import analyze_impact, SectorReport, StockOpportunity
from reporting.markdown_report import generate_markdown, save_report


# ══════════════════════════════════════════════════════════════════
# Configuration de la page
# ══════════════════════════════════════════════════════════════════

st.set_page_config(
    page_title="French Market Intel",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── CSS personnalisé ─────────────────────────────────────────────

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:ital,opsz,wght@0,9..40,300;0,9..40,500;0,9..40,700;1,9..40,400&family=JetBrains+Mono:wght@400;600&display=swap');

:root {
    --bg-dark: #0a0f1c;
    --bg-card: #111827;
    --accent-green: #10b981;
    --accent-red: #ef4444;
    --accent-blue: #3b82f6;
    --accent-amber: #f59e0b;
    --text-primary: #f1f5f9;
    --text-muted: #94a3b8;
    --border: #1e293b;
}

.stApp {
    font-family: 'DM Sans', sans-serif;
}

/* Metric cards */
div[data-testid="stMetricValue"] {
    font-family: 'JetBrains Mono', monospace;
    font-size: 1.8rem;
    font-weight: 700;
}

div[data-testid="stMetricDelta"] > div {
    font-family: 'JetBrains Mono', monospace;
}

/* Signal badges */
.signal-badge {
    display: inline-block;
    padding: 4px 14px;
    border-radius: 20px;
    font-size: 0.8rem;
    font-weight: 700;
    font-family: 'JetBrains Mono', monospace;
    letter-spacing: 0.05em;
}
.signal-bull { background: #064e3b; color: #6ee7b7; border: 1px solid #10b981; }
.signal-bear { background: #450a0a; color: #fca5a5; border: 1px solid #ef4444; }
.signal-neutral { background: #1c1917; color: #d6d3d1; border: 1px solid #57534e; }

/* Impact badges */
.impact-fort { color: #ef4444; font-weight: 700; }
.impact-moyen { color: #f59e0b; font-weight: 600; }
.impact-faible { color: #6b7280; }

/* Header */
.main-header {
    background: linear-gradient(135deg, #0f172a 0%, #1e1b4b 50%, #0f172a 100%);
    padding: 2rem;
    border-radius: 16px;
    margin-bottom: 1.5rem;
    border: 1px solid #312e81;
}
.main-header h1 {
    font-size: 2.2rem;
    font-weight: 700;
    margin: 0;
    background: linear-gradient(90deg, #818cf8, #c084fc, #f472b6);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
}
.main-header p {
    color: #94a3b8;
    margin: 0.3rem 0 0;
    font-size: 0.95rem;
}

/* Disclaimer */
.disclaimer-box {
    background: #451a03;
    border: 1px solid #92400e;
    border-radius: 10px;
    padding: 1rem 1.5rem;
    font-size: 0.85rem;
    color: #fcd34d;
    margin-top: 2rem;
}

/* Data table tweaks */
div[data-testid="stDataFrame"] {
    border-radius: 10px;
    overflow: hidden;
}

/* Tabs */
button[data-baseweb="tab"] {
    font-family: 'DM Sans', sans-serif;
    font-weight: 600;
}
</style>
""", unsafe_allow_html=True)


# ══════════════════════════════════════════════════════════════════
# Fonctions utilitaires
# ══════════════════════════════════════════════════════════════════

SIGNAL_COLORS = {"haussier": "#10b981", "baissier": "#ef4444", "neutre": "#6b7280"}
SIGNAL_ICONS = {"haussier": "🟢", "baissier": "🔴", "neutre": "⚪"}
IMPACT_ICONS = {"fort": "🔥", "moyen": "⚡", "faible": "💤"}


def signal_badge_html(signal: str) -> str:
    cls = {"haussier": "signal-bull", "baissier": "signal-bear"}.get(signal, "signal-neutral")
    return f'<span class="signal-badge {cls}">{signal.upper()}</span>'


def impact_html(impact: str) -> str:
    cls = f"impact-{impact}"
    icon = IMPACT_ICONS.get(impact, "")
    return f'<span class="{cls}">{icon} {impact}</span>'


@st.cache_data(ttl=300, show_spinner=False)
def run_analysis():
    """Exécute le pipeline complet et met en cache 5 minutes."""
    articles = fetch_news()
    if not articles:
        return [], {}, []

    articles = classify_articles(articles)
    articles = analyze_sentiment(articles)

    tickers = get_all_tickers()
    quotes = fetch_quotes(tickers)

    reports = analyze_impact(articles, quotes)
    return articles, quotes, reports


# ══════════════════════════════════════════════════════════════════
# Sidebar
# ══════════════════════════════════════════════════════════════════

with st.sidebar:
    st.markdown("## ⚙️ Paramètres")

    if st.button("🔄 Rafraîchir les données", use_container_width=True, type="primary"):
        st.cache_data.clear()
        st.rerun()

    st.markdown("---")

    # Filtre par secteur
    sector_map = get_sector_map()
    sector_options = ["Tous"] + [s["label"] for s in sector_map.values()]
    selected_sector = st.selectbox("📂 Secteur", sector_options)

    # Filtre par signal
    signal_filter = st.multiselect(
        "🎯 Signaux",
        ["haussier", "baissier", "neutre"],
        default=["haussier", "baissier"],
    )

    # Filtre impact
    impact_filter = st.multiselect(
        "💥 Niveau d'impact",
        ["fort", "moyen", "faible"],
        default=["fort", "moyen"],
    )

    st.markdown("---")

    # Export
    st.markdown("### 📥 Export")
    export_md = st.button("Exporter en Markdown", use_container_width=True)

    st.markdown("---")
    st.markdown(
        '<div class="disclaimer-box">⚠️ Ceci n\'est pas un conseil d\'investissement.</div>',
        unsafe_allow_html=True,
    )

    st.markdown(
        "<br><center><small style='color:#475569'>French Market Intel v2.0</small></center>",
        unsafe_allow_html=True,
    )


# ══════════════════════════════════════════════════════════════════
# Chargement des données
# ══════════════════════════════════════════════════════════════════

st.markdown(
    '<div class="main-header">'
    '<h1>📊 French Market Intel</h1>'
    f'<p>Analyse automatisée — {datetime.now().strftime("%A %d %B %Y, %H:%M")}</p>'
    '</div>',
    unsafe_allow_html=True,
)

with st.spinner("🔍 Analyse en cours… Récupération des news et des cours…"):
    articles, quotes, reports = run_analysis()

if not articles:
    st.error("❌ Aucune donnée récupérée.")

    # Diagnostic des clés API
    from app_config.settings import NEWSAPI_KEY, GNEWS_KEY
    st.markdown("**Diagnostic des clés API :**")
    st.markdown(f"- NEWSAPI_KEY : {'✅ configurée' if NEWSAPI_KEY else '❌ absente'}")
    st.markdown(f"- GNEWS_KEY : {'✅ configurée' if GNEWS_KEY else '❌ absente'}")

    if NEWSAPI_KEY and not GNEWS_KEY:
        st.warning(
            "⚠️ **NewsAPI gratuit ne fonctionne que depuis localhost.** "
            "Sur Streamlit Cloud, il faut aussi configurer **GNEWS_KEY** dans les Secrets. "
            "Obtenez une clé gratuite sur [gnews.io](https://gnews.io)."
        )

    # Erreurs détaillées du fetcher
    from sources.news_fetcher import get_fetch_errors
    errors = get_fetch_errors()
    if errors:
        st.markdown("**Erreurs détaillées :**")
        for err in errors:
            st.markdown(f"- 🔸 {err}")

    if not NEWSAPI_KEY and not GNEWS_KEY:
        st.info(
            "Ajoutez vos clés dans **Settings → Secrets** au format :\n"
            '```toml\nNEWSAPI_KEY = "votre_cle"\nGNEWS_KEY = "votre_cle"\n```'
        )

    st.stop()


# ══════════════════════════════════════════════════════════════════
# KPIs principaux
# ══════════════════════════════════════════════════════════════════

all_opps = [o for r in reports for o in r.opportunities]
bull_count = sum(1 for o in all_opps if o.signal == "haussier")
bear_count = sum(1 for o in all_opps if o.signal == "baissier")
avg_sentiment = sum(a.sentiment_score for a in articles) / len(articles) if articles else 0

col1, col2, col3, col4, col5 = st.columns(5)
col1.metric("📰 Articles", len(articles))
col2.metric("📂 Secteurs actifs", len(reports))
col3.metric("🟢 Haussiers", bull_count)
col4.metric("🔴 Baissiers", bear_count)
col5.metric("🧠 Sentiment moyen", f"{avg_sentiment:+.2f}")

st.markdown("---")


# ══════════════════════════════════════════════════════════════════
# Onglets principaux
# ══════════════════════════════════════════════════════════════════

tab_opps, tab_sectors, tab_news, tab_heatmap, tab_raw = st.tabs([
    "🏆 Opportunités",
    "📂 Secteurs",
    "📰 Fil d'actualités",
    "🗺️ Heatmap",
    "📋 Données brutes",
])


# ── Tab 1 : Opportunités ─────────────────────────────────────────

with tab_opps:
    st.markdown("### 🏆 Opportunités du jour")

    # Filtrage
    filtered_opps = [
        o for o in all_opps
        if o.signal in signal_filter
        and o.max_impact in impact_filter
        and (selected_sector == "Tous" or o.sector_label == selected_sector)
    ]

    if not filtered_opps:
        st.info("Aucune opportunité ne correspond aux filtres sélectionnés.")
    else:
        # Trier par abs(sentiment) décroissant
        filtered_opps.sort(key=lambda o: abs(o.avg_sentiment), reverse=True)

        for opp in filtered_opps:
            with st.container():
                c1, c2, c3, c4, c5 = st.columns([2.5, 1.2, 1.2, 1, 4])

                with c1:
                    st.markdown(f"**{opp.name}**")
                    st.caption(f"{opp.ticker} · {opp.sector_label}")

                with c2:
                    st.metric("Cours", f"{opp.price:.2f}€", f"{opp.change_pct:+.2f}%")

                with c3:
                    vol_str = f"{opp.volume / 1e6:.1f}M" if opp.volume > 1e6 else f"{opp.volume / 1e3:.0f}K"
                    st.metric("Volume", vol_str)

                with c4:
                    st.markdown(signal_badge_html(opp.signal), unsafe_allow_html=True)
                    st.markdown(impact_html(opp.max_impact), unsafe_allow_html=True)

                with c5:
                    st.markdown(f"*{opp.suggestion}*")
                    if opp.related_headlines:
                        with st.expander("Headlines liées"):
                            for h in opp.related_headlines:
                                st.markdown(f"- {h}")

                st.divider()

    # Graphique des variations
    if filtered_opps:
        st.markdown("#### 📊 Variations du jour (valeurs filtrées)")

        df_opps = pd.DataFrame([{
            "Ticker": o.ticker,
            "Nom": o.name,
            "Variation %": o.change_pct,
            "Signal": o.signal,
            "Secteur": o.sector_label,
        } for o in filtered_opps])

        fig = px.bar(
            df_opps.sort_values("Variation %", ascending=True),
            x="Variation %",
            y="Nom",
            color="Signal",
            color_discrete_map=SIGNAL_COLORS,
            orientation="h",
            hover_data=["Ticker", "Secteur"],
        )
        fig.update_layout(
            height=max(400, len(filtered_opps) * 40),
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans"),
            yaxis_title="",
            xaxis_title="Variation %",
            showlegend=True,
            legend=dict(orientation="h", yanchor="bottom", y=1.02),
        )
        fig.update_traces(marker_line_width=0)
        st.plotly_chart(fig, use_container_width=True)


# ── Tab 2 : Secteurs ─────────────────────────────────────────────

with tab_sectors:
    st.markdown("### 📂 Analyse sectorielle")

    # Graphique radar du sentiment par secteur
    if reports:
        sector_data = pd.DataFrame([{
            "Secteur": r.sector_label,
            "Sentiment": r.overall_sentiment,
            "Articles": len(r.articles),
            "Opportunités": len(r.opportunities),
        } for r in reports])

        col_chart1, col_chart2 = st.columns(2)

        with col_chart1:
            fig_sent = px.bar(
                sector_data.sort_values("Sentiment"),
                x="Sentiment",
                y="Secteur",
                orientation="h",
                color="Sentiment",
                color_continuous_scale=["#ef4444", "#f59e0b", "#10b981"],
                color_continuous_midpoint=0,
            )
            fig_sent.update_layout(
                title="Sentiment par secteur",
                height=450,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans"),
                yaxis_title="",
                showlegend=False,
            )
            st.plotly_chart(fig_sent, use_container_width=True)

        with col_chart2:
            fig_bubble = px.scatter(
                sector_data,
                x="Sentiment",
                y="Articles",
                size="Opportunités",
                color="Secteur",
                size_max=50,
                hover_data=["Opportunités"],
            )
            fig_bubble.update_layout(
                title="Couverture médiatique vs Sentiment",
                height=450,
                plot_bgcolor="rgba(0,0,0,0)",
                paper_bgcolor="rgba(0,0,0,0)",
                font=dict(family="DM Sans"),
            )
            st.plotly_chart(fig_bubble, use_container_width=True)

    # Détail par secteur
    for report in reports:
        if selected_sector != "Tous" and report.sector_label != selected_sector:
            continue

        sent_color = "#10b981" if report.overall_sentiment > 0.1 else (
            "#ef4444" if report.overall_sentiment < -0.1 else "#f59e0b"
        )

        with st.expander(
            f"{'📈' if report.overall_sentiment > 0.1 else '📉' if report.overall_sentiment < -0.1 else '➡️'} "
            f"{report.sector_label} — {len(report.articles)} articles, "
            f"sentiment {report.overall_sentiment:+.2f}",
            expanded=(selected_sector != "Tous"),
        ):
            if report.opportunities:
                df_sec = pd.DataFrame([{
                    "Ticker": o.ticker,
                    "Nom": o.name,
                    "Cours (€)": f"{o.price:.2f}",
                    "Var. %": f"{o.change_pct:+.2f}%",
                    "Signal": f"{SIGNAL_ICONS.get(o.signal, '')} {o.signal}",
                    "Impact": f"{IMPACT_ICONS.get(o.max_impact, '')} {o.max_impact}",
                    "Confiance": o.confidence,
                    "Suggestion": o.suggestion,
                } for o in report.opportunities])

                st.dataframe(df_sec, use_container_width=True, hide_index=True)

            st.markdown("**Articles clés :**")
            for art in report.articles[:5]:
                st.markdown(f"- **{art.title}** ({art.source}) — Sentiment: {art.sentiment_label} ({art.sentiment_score:+.2f})")


# ── Tab 3 : Fil d'actualités ─────────────────────────────────────

with tab_news:
    st.markdown("### 📰 Fil d'actualités du jour")

    # Filtre sentiment
    news_sent_filter = st.radio(
        "Filtrer par sentiment",
        ["Tous", "Positif", "Négatif", "Neutre"],
        horizontal=True,
    )

    filtered_articles = articles
    if news_sent_filter != "Tous":
        filtered_articles = [a for a in articles if a.sentiment_label == news_sent_filter.lower()]

    for i, art in enumerate(filtered_articles[:40], 1):
        sent_icon = {"positif": "📈", "négatif": "📉", "neutre": "➡️"}.get(art.sentiment_label, "")
        impact_icon = IMPACT_ICONS.get(art.impact_level, "")

        with st.container():
            col_n1, col_n2 = st.columns([5, 1])
            with col_n1:
                st.markdown(f"**{i}. {art.title}** {sent_icon} {impact_icon}")
                if art.description:
                    st.caption(art.description[:250])
                meta_parts = [f"📌 {art.source}"]
                if art.sectors and art.sectors != ["general"]:
                    labels = []
                    for sid in art.sectors:
                        s = sector_map.get(sid)
                        if s:
                            labels.append(s["label"])
                    if labels:
                        meta_parts.append(f"📂 {', '.join(labels)}")
                if art.impacted_tickers:
                    meta_parts.append(f"🎯 {', '.join(art.impacted_tickers[:5])}")
                st.caption(" · ".join(meta_parts))

            with col_n2:
                score = art.sentiment_score
                color = "#10b981" if score > 0.1 else ("#ef4444" if score < -0.1 else "#f59e0b")
                st.markdown(
                    f"<div style='text-align:center;padding:8px;border-radius:8px;"
                    f"background:{color}22;border:1px solid {color}'>"
                    f"<span style='font-family:JetBrains Mono;font-size:1.1rem;"
                    f"font-weight:700;color:{color}'>{score:+.2f}</span>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
        st.divider()

    # Distribution des sentiments
    st.markdown("#### 📊 Distribution des sentiments")
    df_sent = pd.DataFrame([{
        "Titre": a.title[:60],
        "Score": a.sentiment_score,
        "Label": a.sentiment_label,
    } for a in articles])

    fig_hist = px.histogram(
        df_sent, x="Score", color="Label",
        color_discrete_map={"positif": "#10b981", "négatif": "#ef4444", "neutre": "#f59e0b"},
        nbins=20,
    )
    fig_hist.update_layout(
        height=300,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(family="DM Sans"),
        showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig_hist, use_container_width=True)


# ── Tab 4 : Heatmap ──────────────────────────────────────────────

with tab_heatmap:
    st.markdown("### 🗺️ Heatmap des variations par secteur")

    # Construire la matrice secteur × top tickers
    heatmap_data = []
    for report in reports:
        for opp in report.opportunities:
            heatmap_data.append({
                "Secteur": report.sector_label,
                "Valeur": opp.name,
                "Variation %": opp.change_pct,
                "Sentiment": opp.avg_sentiment,
            })

    if heatmap_data:
        df_heat = pd.DataFrame(heatmap_data)

        # Treemap des variations
        fig_tree = px.treemap(
            df_heat,
            path=["Secteur", "Valeur"],
            values=[abs(v) + 0.1 for v in df_heat["Variation %"]],
            color="Variation %",
            color_continuous_scale=["#ef4444", "#fbbf24", "#10b981"],
            color_continuous_midpoint=0,
            hover_data=["Sentiment"],
        )
        fig_tree.update_layout(
            height=600,
            font=dict(family="DM Sans", size=13),
            paper_bgcolor="rgba(0,0,0,0)",
        )
        fig_tree.update_traces(
            textfont=dict(size=14, family="JetBrains Mono"),
            texttemplate="%{label}<br>%{color:+.2f}%",
        )
        st.plotly_chart(fig_tree, use_container_width=True)

        # Scatter sentiment vs variation
        st.markdown("#### Sentiment vs Variation du cours")
        fig_scatter = px.scatter(
            df_heat,
            x="Sentiment",
            y="Variation %",
            color="Secteur",
            size=[abs(v) + 0.5 for v in df_heat["Variation %"]],
            text="Valeur",
            size_max=30,
        )
        fig_scatter.update_traces(textposition="top center", textfont_size=10)
        fig_scatter.update_layout(
            height=500,
            plot_bgcolor="rgba(0,0,0,0)",
            paper_bgcolor="rgba(0,0,0,0)",
            font=dict(family="DM Sans"),
        )
        # Quadrants
        fig_scatter.add_hline(y=0, line_dash="dash", line_color="#475569", opacity=0.5)
        fig_scatter.add_vline(x=0, line_dash="dash", line_color="#475569", opacity=0.5)
        fig_scatter.add_annotation(x=0.5, y=3, text="🟢 Achat", showarrow=False, font=dict(size=14, color="#10b981"))
        fig_scatter.add_annotation(x=-0.5, y=-3, text="🔴 Vente", showarrow=False, font=dict(size=14, color="#ef4444"))
        st.plotly_chart(fig_scatter, use_container_width=True)
    else:
        st.info("Pas assez de données pour générer la heatmap.")


# ── Tab 5 : Données brutes ───────────────────────────────────────

with tab_raw:
    st.markdown("### 📋 Données brutes")

    col_r1, col_r2 = st.tabs(["Articles", "Cours boursiers"])

    with col_r1:
        df_articles = pd.DataFrame([{
            "Titre": a.title,
            "Source": a.source,
            "Secteurs": ", ".join(a.sectors),
            "Tickers": ", ".join(a.impacted_tickers[:5]),
            "Sentiment": a.sentiment_score,
            "Label": a.sentiment_label,
            "Impact": a.impact_level,
            "Date": a.published_at,
        } for a in articles])
        st.dataframe(df_articles, use_container_width=True, hide_index=True, height=500)

    with col_r2:
        df_quotes = pd.DataFrame([{
            "Ticker": q.ticker,
            "Cours (€)": q.price,
            "Var. %": q.change_pct,
            "Volume": q.volume,
            "Clôture veille": q.prev_close,
            "Plus haut": q.day_high,
            "Plus bas": q.day_low,
            "Erreur": q.error or "",
        } for q in quotes.values() if not q.error])
        df_quotes = df_quotes.sort_values("Var. %", ascending=False)
        st.dataframe(df_quotes, use_container_width=True, hide_index=True, height=500)


# ── Export Markdown ───────────────────────────────────────────────

if export_md:
    md = generate_markdown(reports)
    path = save_report(md)
    st.sidebar.success(f"Rapport exporté : {path.name}")
    st.sidebar.download_button(
        "⬇️ Télécharger le rapport",
        data=md,
        file_name=path.name,
        mime="text/markdown",
    )


# ── Footer ────────────────────────────────────────────────────────

st.markdown(
    f'<div class="disclaimer-box">{DISCLAIMER}</div>',
    unsafe_allow_html=True,
)
