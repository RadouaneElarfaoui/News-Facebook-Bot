# 🎬 Screen Drop — News Facebook Bot

**Pipeline automatisé de veille, rédaction IA, création visuelle RTL et publication d'actualités sur Facebook.**

Le bot surveille les tendances mondiales en temps réel via **GNews**, réécrit chaque sujet en arabe avec **Google Gemini / Gemma** dans un style *Snackable News* percutant, sélectionne et compose automatiquement un visuel `1200×630 px` avec typographie arabe RTL et mots-clés surlignés en jaune doré, puis publie la photo sur **Facebook** accompagnée d'un récit détaillé en premier commentaire.

---

## 📚 Documentation du projet

- 🔄 **[PIPELINE.md](PIPELINE.md)** — Architecture détaillée, flux de données étape par étape et **diagrammes Mermaid** (Flowchart, Séquence, Base de données).
- 🚀 **[DEPLOYMENT.md](DEPLOYMENT.md)** — Guide de mise en production 24h/24 sous Ubuntu avec `systemd`.

---

## ✨ Fonctionnalités principales

- 📡 **Radar d'actualités (< 24h)** — Collecte les dernières actualités en arabe via l'API **GNews** et écarte automatiquement les articles datant de plus de 24 heures.
- 🧠 **Moteur éditorial IA (Gemini / Gemma)** — Génère pour chaque sujet :
  1. Un titre court et accrocheur en arabe + la liste des mots-clés à mettre en valeur.
  2. Une légende Facebook engageante incitant à lire le premier commentaire.
  3. Un résumé narratif fluide (*Snackable News*) publié en premier commentaire.
- 🎨 **Direction artistique & Composition visuelle (`1200×630 px`)** :
  - Recherche d'images sur **Pexels** puis **Unsplash** (ou génération d'un dégradé sombre en fallback).
  - **Sélection intelligente par IA** : Gemini choisit la photo la plus pertinente parmi les candidats.
  - Recadrage centré, léger flou gaussien, overlay dégradé noir, rendu **arabe RTL natif** (`Pillow` + `libraqm`) avec mots-clés en jaune doré (`#FFD700`) et watermark logo.
- 🗄️ **Déduplication & Persistance SQLite (WAL)** — Stocke les articles traités, l'historique des publications Facebook et l'état interne du bot sans doublons.
- ⏰ **Scheduler & Rattrapage automatique** — Planification via `APScheduler` (8 créneaux/jour par défaut) avec rattrapage automatique des exécutions manquées au démarrage.
- 🛡️ **Résilience & Monitoring** — Retry avec backoff exponentiel sur les appels IA, fichier heartbeat (`data/bot.alive`) et fichier d'alerte (`data/bot.alert`) après 3 échecs consécutifs.

---

## 🏗️ Structure du projet

```text
fb-bot/
├── main.py                        # Point d'entrée : orchestrateur du pipeline & scheduler
├── PIPELINE.md                    # Documentation détaillée du pipeline & diagrammes Mermaid
├── DEPLOYMENT.md                  # Guide de déploiement systemd (Ubuntu)
├── requirements.txt               # Dépendances Python
├── .env                           # Clés API secrètes (ignoré par Git)
├── .env.example                   # Modèle de fichier d'environnement
├── config/
│   ├── settings.yaml              # Identité de marque, paramètres visuels, horaires
│   └── prompts.yaml               # Templates de prompts IA (titre, légende, commentaire)
├── modules/
│   ├── core/
│   │   ├── config_loader.py       # Chargement centralisé de settings.yaml, prompts.yaml et .env
│   │   ├── database.py            # Gestion SQLite (articles, posts, metadata)
│   │   └── logger.py              # Logger rotatif (console + fichiers logs/)
│   ├── radar/
│   │   └── aggregator.py          # Collecte et filtrage (< 24h) via GNews API
│   ├── content/
│   │   └── engine.py              # ContentEngine : appels Gemini/Gemma avec retry/backoff
│   ├── visual/
│   │   ├── image_fetcher.py       # Recherche Pexels / Unsplash + sélection IA Gemini
│   │   ├── compositor.py          # Composition Pillow 1200x630 (RTL, surlignage, watermark)
│   │   └── assets/
│   │       ├── fonts/Cairo-Bold.ttf
│   │       └── logo.png
│   └── publisher/
│       └── fb_api.py              # Publication Photo + 1er Commentaire via Facebook Graph API
├── data/
│   ├── bot_data.db                # Base SQLite (créée automatiquement)
│   ├── bot.alive                  # Heartbeat de la dernière exécution
│   └── bot.alert                  # Généré en cas de >= 3 échecs consécutifs
├── output/                        # Visuels générés (post_<timestamp>.jpg)
├── logs/                          # Journaux d'exécution
└── tests/                         # Scripts de validation (APIs, compositor, publication)
```

---

## ⚙️ Installation & Configuration

### 1. Prérequis système

- **Python 3.10+**
- Librairies natives pour le rendu typographique arabe RTL avec `libraqm` :

```bash
# Ubuntu / Debian
sudo apt update
sudo apt install libfribidi-dev libharfbuzz-dev libfontconfig1-dev
```

### 2. Environnement virtuel et dépendances

```bash
git clone <repo-url>
cd fb-bot

python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 3. Configuration des clés API (`.env`)

Copiez le fichier d'exemple et renseignez vos identifiants :

```bash
cp .env.example .env
nano .env
```

| Variable | Description |
| :--- | :--- |
| `FB_PAGE_ID` | Identifiant de la page Facebook cible |
| `FB_ACCESS_TOKEN` | Token d'accès de page Facebook Graph API |
| `GEMINI_API_KEY` | Clé API Google AI Studio (Gemini / Gemma) |
| `GNEWS_API_KEY` | Clé API GNews (`https://gnews.io`) |
| `PEXELS_API_KEY` | Clé API Pexels (`https://www.pexels.com/api/`) |
| `UNSPLASH_ACCESS_KEY` | Clé API Unsplash (`https://unsplash.com/developers`) |

> **⚠️ Note importante sur le modèle IA** : Le modèle défini dans `config/settings.yaml` (`apis.gemini.model`) est configuré sur `gemma-4-31b-it`. Ne modifiez pas ce paramètre sans autorisation préalable.

---

## ▶️ Utilisation

### Exécution unique (immédiate)

Lance un cycle complet de collecte, génération et publication :

```bash
source venv/bin/activate
python main.py --once
```

### Mode Planifié (Daemon / Scheduler)

Lance le planificateur en continu aux heures définies dans `config/settings.yaml` (`posting_hours: [8, 10, 12, 14, 16, 18, 20, 22]`) avec rattrapage automatique au démarrage :

```bash
source venv/bin/activate
python main.py --schedule
```

### Mode Brouillon / Simulation (`is_draft`)

Pour tester tout le pipeline (collecte + IA + génération d'image dans `output/`) **sans publier réellement sur Facebook**, passez `is_draft: true` dans `config/settings.yaml` :

```yaml
publisher:
  is_draft: true
```

---

## 🧪 Tests & Vérifications

```bash
# Tester la validité des clés API
python tests/test_api_keys.py

# Tester la génération d'image et le rendu arabe RTL
python tests/test_compositor.py

# Tester la publication Facebook (Photo + Commentaire)
python tests/test_publisher.py
```

---

## 📄 Licence

Projet privé — **Screen Drop**. Tous droits réservés.
