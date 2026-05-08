"""
Radar — Aggregator
===================
Récupère les actualités fraîches via l'API GNews.
"""
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
    url = "https://gnews.io/api/v4/top-headlines"
    params = {
        "token": api_key,
        "lang": "ar",
        "max": 10,
        "category": "general"
    }

    try:
        logger.info("Récupération des news sur GNews...")
        resp = httpx.get(url, params=params, timeout=15)
        resp.raise_for_status()
        articles = resp.json().get("articles", [])
        logger.info("✓ %d articles récupérés.", len(articles))
        return articles
    except Exception as e:
        logger.error("Erreur lors de la récupération GNews : %s", e)
        return []
