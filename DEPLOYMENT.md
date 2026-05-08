# 🚀 Déploiement et Automatisation (Ubuntu)

Ce guide explique comment configurer le **News Facebook Bot** pour qu'il tourne 24h/24 en arrière-plan et redémarre automatiquement avec votre ordinateur.

## 1. Création du Service Systemd

Sur Ubuntu, la meilleure façon d'automatiser un script est d'utiliser `systemd`.

1. Créez le fichier de service :
   ```bash
   sudo nano /etc/systemd/system/news_bot.service
   ```

2. Copiez et collez le contenu suivant (en vérifiant que les chemins correspondent à votre installation) :

```ini
[Unit]
Description=News Facebook Bot Service
After=network.target

[Service]
User=alfredo
WorkingDirectory=/home/alfredo/Programmation/py_projet/fb-bot
ExecStart=/home/alfredo/Programmation/py_projet/fb-bot/venv/bin/python3 main.py --schedule
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

3. Sauvegardez (`Ctrl+O`, `Entrée`) et quittez (`Ctrl+X`).

## 2. Activation et Lancement

Une fois le fichier créé, exécutez ces commandes :

```bash
# Recharger la liste des services
sudo systemctl daemon-reload

# Activer le lancement automatique au démarrage
sudo systemctl enable news_bot.service

# Lancer le bot immédiatement
sudo systemctl start news_bot.service
```

## 3. Gestion du Bot

Voici les commandes essentielles pour surveiller votre bot :

| Action | Commande |
|---|---|
| **Vérifier le statut** | `sudo systemctl status news_bot.service` |
| **Voir les logs en direct** | `journalctl -u news_bot.service -f` |
| **Arrêter le bot** | `sudo systemctl stop news_bot.service` |
| **Redémarrer le bot** | `sudo systemctl restart news_bot.service` |

---

## 💡 Conseils
- Si vous modifiez le fichier `settings.yaml` ou `prompts.yaml`, n'oubliez pas de faire un `sudo systemctl restart news_bot.service` pour que les changements soient pris en compte.
- Vérifiez régulièrement les logs pour vous assurer que vos quotas d'API ne sont pas dépassés.
