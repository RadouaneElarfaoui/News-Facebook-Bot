"""
Radar — Aggregator
===================
Récupère les actualités fraîches via l'API GNews.
"""
from datetime import datetime, timezone, timedelta

import httpx
from modules.core.config_loader import config
from modules.core.logger import get_logger

logger = get_logger(__name__)

def fetch_trending_news() -> list[dict]:
    """
    Récupère les dernières actualités mondiales en arabe.
    """
    api_key = config["apis"]["gnews"]["api_key"]
    if not api_key or "YOUR" in api_key:
        logger.warning("GNews API Key non configurée.")
        return []

    # On récupère les news mondiales (top-headlines) en arabe
    radar_cfg = config.get("radar", {})
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": api_key,
        "lang": radar_cfg.get("lang", "ar"),
        "max": radar_cfg.get("fetch_max", radar_cfg.get("max_articles_per_run", 20)),
        "category": radar_cfg.get("category", "general")
    }

    try:
        logger.info("Récupération des news sur GNews...")
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
        before = len(articles)
        articles = [
            a for a in articles
            if a.get("publishedAt") and datetime.fromisoformat(a["publishedAt"].replace("Z", "+00:00")) >= cutoff
        ]
        filtered = before - len(articles)
        if filtered:
            logger.info("🗑️ %d articles filtrés (>24h).", filtered)
        logger.info("✓ %d articles récupérés.", len(articles))
        return articles
    except Exception as e:
        logger.error("Erreur lors de la récupération GNews : %s", e)
        return []
