# 🎬 News Facebook Bot

**Automatisation complète du pipeline de publication d'actualités pour les réseaux sociaux.**

Le bot collecte les tendances mondiales, réécrit le contenu en arabe avec l'IA Gemini (style Snackable News), génère des visuels stylisés et les publie sur Facebook avec un résumé détaillé en premier commentaire — entièrement en automatique.

---

## ✨ Fonctionnalités

- 📡 **Collecte de news** — Récupère les dernières actualités via l'API GNews (arabe, français, anglais).
- 🤖 **Génération de contenu IA** — Réécrit les titres et génère des légendes engageantes via Google Gemini.
- 📝 **Storytelling (Snackable News)** — Génère un résumé fluide et moderne en premier commentaire pour chaque post.
- 🖼️ **Composition visuelle** — Crée des images 1200×630 px :
  - Image de fond intelligente choisie par l'IA (Pexels / Unsplash).
  - Overlay gradient noir pour le contraste.
  - Texte arabe RTL avec mots-clés surlignés en jaune doré.
  - Watermark logo en filigrane.
- 🗄️ **Déduplication** — Base SQLite pour ne pas retraiter deux fois le même article.
- 🚀 **Publication Facebook** — Envoi automatique de l'image et du premier commentaire via Facebook Graph API.
- 📅 **Scheduler** — Publication planifiée (8 posts/jour) via APScheduler.
- 🧪 **Tests intégrés** — Validation de toutes les clés API et du rendu visuel.

---

## 🏗️ Architecture du projet

```
fb-bot/
├── main.py                     # Point d'entrée — orchestre le pipeline + scheduler
├── requirements.txt
├── .env                        # Secrets locaux (gitignored — ne pas committer)
├── .env.example                # Template à copier pour configurer le bot
├── config/
│   ├── settings.yaml           # Paramètres visuels, scheduler (sans secrets)
│   └── prompts.yaml            # Templates de prompts Gemini (Snackable News)
├── modules/
│   ├── core/
│   │   ├── config_loader.py    # Chargement YAML centralisé
│   │   ├── database.py         # SQLite : articles vus, posts publiés
│   │   └── logger.py           # Logger structuré
│   ├── radar/
│   │   └── aggregator.py       # Récupération GNews API
│   ├── content/
│   │   └── engine.py           # ContentEngine : Gemini → Titre, Caption & Comment
│   ├── visual/
│   │   ├── compositor.py       # Composition d'image Pillow (RTL + watermark)
│   │   ├── image_fetcher.py    # Pexels → Unsplash → Sélection intelligente
│   │   └── assets/
│   │       ├── fonts/
│   │       │   └── Cairo-Bold.ttf
│   │       └── logo.png
│   └── publisher/
│       └── fb_api.py           # Publication Facebook (Post + Commentaire)
├── data/
│   └── bot_data.db             # Base SQLite (auto-créée)
├── output/                     # Images générées (auto-créé)
├── logs/                       # Fichiers de log rotatifs
└── tests/
    ├── test_api_keys.py        # Validation de toutes les APIs
    ├── test_compositor.py      # Test de la composition visuelle
    └── test_publisher.py       # Test de publication Facebook (Post + Comment)
```

---

## 🔄 Pipeline complet

```
GNews API  ──→  [radar/aggregator]  ──→  Articles frais
    │
    ▼
[content/engine]    ──→  Gemini : Titre Snackable + Keywords
    │                 ──→  Gemini : Légende Facebook avec mention "Commentaire 👇"
    │                 ──→  Gemini : Résumé narratif (Snackable Style) pour le commentaire
    ▼
[visual/image_fetcher] ──→  Sélection intelligente (IA) sur Pexels / Unsplash
    │
    ▼
[visual/compositor]  ──→  Image 1200×630 px (RTL + Watermark)
    │
    ▼
[publisher/fb_api]   ──→  Publication de la PHOTO
    │                 ──→  Publication du COMMENTAIRE DÉTAILLÉ
    ▼
[core/database]      ──→  Enregistrement SQLite (anti-doublon)
```

---

## 🚀 Installation

### Prérequis

- Python 3.10+
- `libraqm` (pour le rendu RTL natif avec Pillow)

```bash
# Ubuntu / Debian
sudo apt install libfribidi-dev libharfbuzz-dev libfontconfig1-dev
```

### Mise en place

```bash
# 1. Cloner le dépôt
git clone <repo-url>
cd fb-bot

# 2. Créer et activer le venv
python3 -m venv venv
source venv/bin/activate

# 3. Installer les dépendances
pip install -r requirements.txt

# 4. Configurer les secrets
cp .env.example .env
nano .env   # Remplir vos clés API
```

---

## ⚙️ Configuration

Les secrets ne sont **jamais** stockés dans le code. Ils sont gérés via un fichier `.env` local.

```bash
# Copier le template
cp .env.example .env

# Éditer .env et remplir vos vraies clés
nano .env
```

Les clés à renseigner dans `.env` :

| Variable | Description |
|---|---|
| `FB_PAGE_ID` | ID de votre page Facebook |
| `FB_ACCESS_TOKEN` | Token d'accès Facebook Graph API |
| `GEMINI_API_KEY` | Clé Google AI Studio |
| `GNEWS_API_KEY` | Clé GNews API |
| `PEXELS_API_KEY` | Clé Pexels |
| `UNSPLASH_ACCESS_KEY` | Clé Unsplash |

> **⚠️ Note sur le modèle LLM** : Le modèle configuré dans `settings.yaml` est `gemma-4-31b-it`. Ne modifiez pas ce paramètre sans autorisation préalable.

---

## ▶️ Utilisation

### Lancer le pipeline une seule fois (Manuel)

```bash
source venv/bin/activate
python main.py --once
```

### Lancer le bot en automatique (Daemon/Serveur)

```bash
python main.py --schedule
```
*Le bot tournera en arrière-plan et publiera aux heures définies dans `settings.yaml`.*

### Déploiement Permanent (Ubuntu)

Pour que le bot tourne 24h/24 et redémarre tout seul avec votre PC, consultez le guide de déploiement :
👉 **[DEPLOYMENT.md](file:///home/alfredo/Programmation/py_projet/fb-bot/DEPLOYMENT.md)**

### Vérifier toutes les APIs et la publication


```bash
python tests/test_api_keys.py
python tests/test_publisher.py
```

---

## 📦 Dépendances principales

- `Pillow` (Support `libraqm`) : Rendu image et texte RTL.
- `google-genai` : SDK Google Gemini pour la génération de contenu.
- `apscheduler` : Planification robuste des publications.
- `httpx` : Requêtes asynchrones pour les APIs.
- `python-dotenv` : Chargement des secrets depuis `.env`.

---

## 🧩 Détails techniques

### Snackable News Style
Le bot évite les listes à puces ennuyeuses dans les commentaires. Il utilise un style narratif inspiré des grands médias sociaux (AJ+, Brut), avec des paragraphes courts et une transition fluide pour captiver le lecteur.

### Rendu Arabe Natif
Le compositor utilise **Pillow avec libraqm** pour garantir une mise en forme RTL parfaite, incluant le support complexe des ligatures et le surlignage mot-à-mot de droite à gauche.

---

## 🗺️ Roadmap

- [x] Module `publisher` — Publication automatique (Post + Comment)
- [x] Scheduler APScheduler — 8 posts/jour
- [ ] Support multi-catégories avancé (sport, monde, insolite)
- [ ] Déduplication par similarité (SimHash)
- [ ] Dashboard de monitoring Web
- [ ] Support vidéo (Reels courts)

---

## 📄 Licence

Projet privé — Screen Drop. Tous droits réservés.
