# 🎬 Screen Drop — Facebook News Bot

Bot automatisé de veille, génération de contenu via **Antigravity CLI (`agy`)** et publication d'actualités en arabe sur Facebook avec visuels RTL et premier commentaire détaillé.

---

## ⚡ Démarrage rapide

### 1. Configuration (`.env`)
```bash
cp .env.example .env
# Renseigner FB_PAGE_ID, FB_ACCESS_TOKEN, GNEWS_API_KEY, PEXELS_API_KEY
```

### 2. Connecter `agy` (Google AI Pro)
```bash
# En local :
python main.py --agy-login
python main.py --agy-check

# Ou via Docker (VPS) :
docker compose run --rm bot python main.py --agy-login
docker compose run --rm bot python main.py --agy-check
```

### 3. Exécution
```bash
# Test ponctuel (mode brouillon sans publication si is_draft: true)
python main.py --once

# Lancement continu (scheduler)
python main.py --schedule

# En production Docker (VPS)
docker compose up -d
```

---

## 🏗️ Architecture simplifiée

```
GNews API  ──→  [radar] Récupération des news (< 24h)
    │
    ▼
[content]       1 seul appel `agy` (Google AI Pro)
                → Titre arabe court + mots-clés
                → Requête image en anglais
                → Légende Facebook
                → Premier commentaire narratif
    ▼
[visual]        Pexels / Unsplash (sélection assistée par `agy`)
                → Image 1200×630 avec typographie arabe RTL (Cairo-Bold)
                → Gradient sombre, mots-clés dorés, watermark
    ▼
[publisher]     Facebook Graph API
                → Publication photo
                → Publication du 1er commentaire
    ▼
[core/database] SQLite (WAL) : déduplication et historique
```

---

## ⚙️ Configuration (`config/settings.yaml`)

| Clé | Rôle | Valeur par défaut |
|---|---|---|
| `llm.agy.model` | Modèle utilisé par `agy` | `gemini-3.8-flash-medium` |
| `publisher.posts_per_run` | Nombre max de posts par session | `1` |
| `publisher.is_draft` | Simulation sans publication | `true` (passer à `false` en prod) |
| `publisher.posting_hours` | Heures de publication cron | `[8, 10, 12, 14, 16, 18, 20, 22]` |
| `visual.keep_output_days` | Purge des anciennes images | `14` |

---

## 🧪 Tests

```bash
# Tests unitaires du backend agy et du moteur de contenu
python -m unittest tests/test_llm_backend.py -v

# Vérifier les clés API externes
python tests/test_api_keys.py

# Tester le compositeur d'image RTL
python tests/test_compositor.py
```

---

## 📁 Structure

```text
fb-bot/
├── main.py              # Orchestrateur, scheduler, --agy-login, --agy-check
├── Dockerfile           # Image Python 3.12 + libraqm (support ARM64 / x86_64)
├── compose.yaml         # Déploiement Docker (VPS)
├── PIPELINE.md          # Flux détaillé et diagrammes Mermaid
├── DEPLOYMENT.md        # Guide de déploiement Docker VPS & systemd
├── config/              # settings.yaml, prompts.yaml
├── modules/
│   ├── core/            # Config, base SQLite, logger
│   ├── llm/             # Wrapper CLI agy (-p, --json-schema, sandbox)
│   ├── radar/           # GNews API
│   ├── content/         # Génération unifiée du texte
│   ├── visual/          # Recherche d'images et composition RTL
│   └── publisher/       # Facebook Graph API
├── data/                # Base SQLite, session agy, alertes
└── output/              # Images générées (1200×630)
```
