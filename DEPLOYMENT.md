# 🚀 Déploiement et Automatisation (VPS Docker & Ubuntu Systemd)

Ce guide explique comment déployer **Screen Drop Bot** propulsé par **Antigravity CLI (`agy`)** sur un VPS (via Docker Compose, recommandé) ou directement sur Ubuntu (via `systemd`).

---

## Option 1 — Déploiement Docker sur VPS (Recommandé)

Docker garantit qu'**une seule instance** du bot tourne, isole les dépendances natives (`libraqm`, `fribidi`, `harfbuzz`) et persiste votre session `agy` ainsi que la base SQLite dans `./data`.

### 1. Prérequis sur le VPS (Linux x86_64)
- Docker & Docker Compose installés
- Le binaire `agy` installé sur l'hôte (par défaut dans `~/.local/bin/agy`, monté en lecture seule dans le conteneur)
- Fichier `.env` configuré (`cp .env.example .env`)

### 2. Connexion initiale de `agy` (compte Google AI Pro)
Depuis le dossier du projet, lancez la commande d'authentification interactive :

```bash
docker compose build
docker compose run --rm bot python main.py --agy-login
```

1. `agy` affiche un **lien de connexion** dans le terminal.
2. Ouvrez ce lien dans votre navigateur, connectez-vous avec votre compte **Google AI Pro**, puis copiez le code/token retourné.
3. Collez le token dans le terminal, puis quittez `agy` (`/exit` ou `Ctrl+D`).
4. Votre session est maintenant sauvegardée de façon persistante dans `./data/agy-home`.

### 3. Vérifier la connexion `agy` et tester un run (Mode Draft)
```bash
# Vérifier que agy répond en JSON structuré
docker compose run --rm bot python main.py --agy-check

# Tester un run complet (1 article)
docker compose run --rm bot python main.py --once
```

### 4. Lancer le bot 24h/24 en arrière-plan
Quand vous êtes prêt à publier réellement, passez `is_draft: false` dans `config/settings.yaml`, puis démarrez le conteneur :

```bash
docker compose up -d
```

### Commandes utiles Docker
| Action | Commande |
|---|---|
| **Voir les logs en direct** | `docker compose logs -f` |
| **Vérifier l'état (healthcheck)** | `docker compose ps` |
| **Redémarrer après modification config** | `docker compose restart` |
| **Arrêter le bot** | `docker compose down` |
| **Se reconnecter à `agy` si session expirée** | `docker compose run --rm bot python main.py --agy-login` |

---

## Option 2 — Service Systemd (Sans Docker)

> ⚠️ **Important** : N'activez qu'**un seul** service systemd (soit système, soit utilisateur `--user`, jamais les deux simultanément).

### 1. Connecter et tester `agy`
```bash
source venv/bin/activate
python main.py --agy-login
python main.py --agy-check
```

### 2. Utiliser le service utilisateur (`~/.config/systemd/user/news_bot.service`)
```bash
systemctl --user daemon-reload
systemctl --user enable news_bot.service
systemctl --user start news_bot.service
```

| Action | Commande |
|---|---|
| **Statut** | `systemctl --user status news_bot.service` |
| **Logs en direct** | `journalctl --user -u news_bot.service -f` |
| **Arrêter** | `systemctl --user stop news_bot.service` |
