# 📊 French Market Intel

**Outil professionnel d'analyse quotidienne automatisée des marchés financiers français.**

Récupère les actualités économiques françaises, les classe par secteur, analyse le sentiment, croise avec les cours boursiers en temps réel (CAC 40, SBF 120, mid-caps) et génère un rapport d'opportunités exploitable en 2 minutes.

---

## ✨ Fonctionnalités

- **Agrégation automatique** de 30-50 news business françaises via NewsAPI + GNews
- **Classification sectorielle** intelligente (énergie, luxe, banque, tech, santé, etc.)
- **Analyse de sentiment** bilingue (FR/EN) — Hugging Face ou dictionnaire intégré
- **Cours boursiers temps réel** via yfinance (70+ valeurs Euronext Paris)
- **Détection d'opportunités** avec signaux haussiers/baissiers et niveaux de confiance
- **Rapport Markdown** structuré + affichage console riche (via `rich`)
- **Envoi email automatique** (SMTP / Gmail App Password)
- **Planification quotidienne** intégrée (APScheduler ou schedule)
- **Déploiement CI/CD** via GitHub Actions (gratuit)

---

## 📁 Architecture

```
french-market-intel/
├── main.py                  # Point d'entrée CLI
├── scheduler.py             # Planificateur quotidien
├── requirements.txt
├── .env.example             # Template de configuration
├── config/
│   ├── settings.py          # Configuration centralisée
│   └── stocks.json          # Univers d'actions configurable
├── sources/
│   ├── news_fetcher.py      # Récupération des news (NewsAPI + GNews)
│   └── market_data.py       # Cours boursiers (yfinance + Polygon)
├── analysis/
│   ├── classifier.py        # Classification sectorielle
│   ├── sentiment.py         # Analyse de sentiment
│   └── impact_analyzer.py   # Croisement news × marchés → opportunités
├── reporting/
│   ├── markdown_report.py   # Génération rapport Markdown + console
│   └── email_sender.py      # Envoi automatique par email
└── output/                  # Rapports générés (créé automatiquement)
```

---

## 🚀 Installation

### Prérequis

- Python 3.11+
- Un compte NewsAPI.org (gratuit) et/ou GNews.io (gratuit)

### Étapes

```bash
# 1. Cloner le projet
git clone https://github.com/votre-user/french-market-intel.git
cd french-market-intel

# 2. Créer un environnement virtuel
python -m venv .venv
source .venv/bin/activate   # Linux/Mac
# .venv\Scripts\activate    # Windows

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les clés API
cp .env.example .env
# Éditer .env avec vos clés
```

### Obtenir les clés API

| Service | URL | Plan gratuit |
|---------|-----|--------------|
| NewsAPI.org | https://newsapi.org/register | 100 req/jour |
| GNews.io | https://gnews.io | 100 req/jour |
| Hugging Face | https://huggingface.co/settings/tokens | Illimité (Inference API) |

> **yfinance** ne nécessite aucune clé API.

---

## 💻 Utilisation

### Exécution unique (mode principal)

```bash
# Rapport console + fichier Markdown
python main.py

# Avec envoi email
python main.py --email

# Mode verbose (debug)
python main.py --verbose
```

### Mode planifié (quotidien)

```bash
# Rapport tous les jours à 8h30 (configurable dans .env)
python main.py --schedule

# Planifié + email + heure personnalisée
python main.py --schedule --email --hour 7 --minute 0
```

### Résultat

Le rapport est généré dans `output/rapport_YYYY-MM-DD_HHMM.md` et affiché dans la console avec un tableau coloré des opportunités.

---

## ⚙️ Configuration

### Univers d'actions (`config/stocks.json`)

Le fichier JSON est entièrement personnalisable. Pour ajouter une valeur :

```json
{
  "ticker": "ALLAIR.PA",
  "name": "Airwell",
  "cap": "small"
}
```

Ajoutez-la dans le secteur approprié. Les mots-clés du secteur servent au matching automatique avec les news.

### Email (Gmail)

1. Activez la validation en 2 étapes sur votre compte Google
2. Générez un **App Password** : https://myaccount.google.com/apppasswords
3. Renseignez dans `.env` :

```env
SMTP_USER=votre_email@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx
EMAIL_TO=destinataire@email.com
```

---

## 🔄 Déploiement automatique (GitHub Actions)

Créez `.github/workflows/daily-report.yml` :

```yaml
name: Daily French Market Report

on:
  schedule:
    # Tous les jours à 6h30 UTC (8h30 Paris en été, 7h30 en hiver)
    - cron: '30 6 * * 1-5'
  workflow_dispatch:  # Déclenchement manuel possible

jobs:
  report:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Setup Python
        uses: actions/setup-python@v5
        with:
          python-version: '3.12'
          cache: 'pip'

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Generate report
        env:
          NEWSAPI_KEY: ${{ secrets.NEWSAPI_KEY }}
          GNEWS_KEY: ${{ secrets.GNEWS_KEY }}
          HF_TOKEN: ${{ secrets.HF_TOKEN }}
          SMTP_USER: ${{ secrets.SMTP_USER }}
          SMTP_PASS: ${{ secrets.SMTP_PASS }}
          EMAIL_TO: ${{ secrets.EMAIL_TO }}
        run: python main.py --email

      - name: Archive report
        uses: actions/upload-artifact@v4
        with:
          name: daily-report
          path: output/*.md
          retention-days: 30
```

**Configuration des secrets GitHub :**
1. Allez dans Settings → Secrets and variables → Actions
2. Ajoutez chaque clé API en tant que secret

---

## 🧪 Vérification rapide

```bash
# Tester que tout fonctionne (sans clé API — affichera des warnings)
python -c "from config.settings import get_all_tickers; print(f'{len(get_all_tickers())} tickers chargés')"

# Tester avec une vraie clé
NEWSAPI_KEY=votre_cle python main.py --verbose
```

---

## 📋 Roadmap

- [x] **V1** — Console + Markdown + Email
- [ ] **V2** — Dashboard Streamlit interactif
- [ ] **V3** — Alertes Telegram / Slack
- [ ] **V4** — Backtesting des signaux

---

## ⚠️ Disclaimer

> **Ceci n'est pas un conseil d'investissement.** Les informations fournies par cet outil sont à titre purement informatif et éducatif. Les signaux et suggestions générés sont le résultat d'un algorithme automatisé et ne constituent en aucun cas une recommandation d'achat ou de vente. Consultez un conseiller financier agréé avant toute décision d'investissement.

---

## 📄 Licence

MIT — Libre d'utilisation, modification et distribution.
