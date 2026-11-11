"""
Visual Factory — Image Fetcher
================================
Cherche une image libre de droits en rapport avec le sujet du news.
Stratégie : Pexels → Unsplash → fallback couleur unie.

Sélection intelligente : Gemini choisit la photo la plus pertinente
parmi les candidats en analysant le contenu de l'article.
"""
from __future__ import annotations

import random
from io import BytesIO
from pathlib import Path

import httpx
from PIL import Image, ImageDraw

from modules.core.config_loader import config
from modules.core.logger import get_logger
from modules.llm import get_backend

logger = get_logger(__name__)

PEXELS_KEY = config["apis"]["pexels"]["api_key"]
UNSPLASH_KEY = config["apis"]["unsplash"]["access_key"]

IMAGE_PICK_SCHEMA = {
    "type": "object",
    "properties": {
        "index": {"type": "integer"},
    },
    "required": ["index"],
}


# ═══════════════════════════════════════════════════════════
# 1. Sélection intelligente par l'agent (agy)
# ═══════════════════════════════════════════════════════════

def _select_best_image(article_text: str, candidates: list[dict]) -> int:
    """
    Demande au backend LLM (agy) de choisir l'image la plus pertinente et
    visuellement impactante pour illustrer l'article.

    Args:
        article_text: Texte ou titre de l'article (peut être en arabe).
        candidates:   Liste de dicts avec au moins 'alt' et 'photographer'.

    Returns:
        Index (0-based) du meilleur candidat.
    """
    if len(candidates) <= 1:
        return 0

    options_lines = "\n".join(
        f"{i}. Description: \"{c.get('alt') or 'Sans description'}\" "
        f"| Photographe: {c.get('photographer', 'Inconnu')}"
        for i, c in enumerate(candidates)
    )

    prompt = (
        "Tu es un directeur artistique pour une page d'actualités Facebook. "
        "Ton rôle est de choisir la photo la plus "
        "pertinente, percutante et visuellement forte pour illustrer l'article.\n"
        "N'utilise aucun outil, réponds uniquement avec l'objet JSON demandé.\n\n"
        f"Sujet de l'article :\n\"{article_text}\"\n\n"
        f"Photos disponibles ({len(candidates)}) :\n{options_lines}\n\n"
        f"Choisis l'index (entier de 0 à {len(candidates) - 1}) de la meilleure photo."
    )

    try:
        backend = get_backend()
        res = backend.generate_json(prompt, IMAGE_PICK_SCHEMA)
        index = int(res.get("index", -1))
        if 0 <= index < len(candidates):
            chosen_alt = candidates[index].get("alt", "—")
            logger.info("🤖 %s a sélectionné l'image #%d : \"%s\"", backend.name, index, chosen_alt[:80])
            return index

        logger.warning("Index hors limites (%s) retourné par %s.", index, backend.name)

    except Exception as e:
        logger.warning("Erreur sélection image via LLM : %s — fallback aléatoire.", e)

    return random.randint(0, len(candidates) - 1)


# ═══════════════════════════════════════════════════════════
# 2. Sources d'images
# ═══════════════════════════════════════════════════════════

def fetch_from_pexels(query: str, article_text: str = "") -> Image.Image | None:
    """
    Récupère jusqu'à 10 photos depuis Pexels et laisse Gemini
    choisir la plus adaptée à l'article.
    """
    if not PEXELS_KEY or "YOUR" in PEXELS_KEY:
        logger.debug("Clé Pexels non configurée.")
        return None

    url     = "https://api.pexels.com/v1/search"
    headers = {"Authorization": PEXELS_KEY}
    params  = {"query": query, "per_page": 10, "orientation": "landscape"}

    try:
        resp = httpx.get(url, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        photos = resp.json().get("photos", [])
        if not photos:
            return None

        logger.info("Pexels : %d candidats trouvés pour \"%s\".", len(photos), query)

        # Construit une liste de candidats avec métadonnées lisibles par le LLM
        candidates = [
            {
                "alt":          photo.get("alt") or "",
                "photographer": photo.get("photographer", ""),
                "src_large2x":  photo["src"]["large2x"],
            }
            for photo in photos
        ]

        # Choix intelligent si le texte de l'article est disponible
        if article_text:
            idx = _select_best_image(article_text, candidates)
        else:
            idx = random.randint(0, min(4, len(candidates) - 1))

        img_data = httpx.get(candidates[idx]["src_large2x"], timeout=15).content
        with BytesIO(img_data) as buf:
            img = Image.open(buf)
            img.load()
            return img

    except Exception as e:
        logger.warning("Pexels fetch error : %s", e)
        return None


def fetch_from_unsplash(query: str, article_text: str = "") -> Image.Image | None:
    """
    Récupère jusqu'à 5 photos via le endpoint de recherche Unsplash
    et laisse Gemini choisir la plus adaptée.
    """
    if not UNSPLASH_KEY or "YOUR" in UNSPLASH_KEY:
        logger.debug("Clé Unsplash non configurée.")
        return None

    # On utilise /search/photos pour obtenir plusieurs candidats
    url    = "https://api.unsplash.com/search/photos"
    params = {
        "query":       query,
        "orientation": "landscape",
        "per_page":    5,
        "client_id":   UNSPLASH_KEY,
    }

    try:
        resp = httpx.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        if not results:
            return None

        logger.info("Unsplash : %d candidats trouvés pour \"%s\".", len(results), query)

        candidates = [
            {
                "alt":          r.get("alt_description") or r.get("description") or "",
                "photographer": r["user"]["name"],
                "url_regular":  r["urls"]["regular"],
            }
            for r in results
        ]

        if article_text:
            idx = _select_best_image(article_text, candidates)
        else:
            idx = 0

        img_data = httpx.get(candidates[idx]["url_regular"], timeout=15).content
        with BytesIO(img_data) as buf:
            img = Image.open(buf)
            img.load()
            return img

    except Exception as e:
        logger.warning("Unsplash fetch error : %s", e)
        return None


# ═══════════════════════════════════════════════════════════
# 3. Fallback local
# ═══════════════════════════════════════════════════════════

def _generate_fallback_image(width: int = 1200, height: int = 630) -> Image.Image:
    """
    Génère une image de fallback avec un dégradé sombre stylisé.
    Utilisé quand aucune API n'est disponible.
    """
    import numpy as np
    arr = np.zeros((height, width, 3), dtype=np.uint8)
    for y in range(height):
        t = y / height
        arr[y, :, 0] = int(15 + 20 * t)
        arr[y, :, 1] = int(20 + 30 * t)
        arr[y, :, 2] = int(40 + 40 * t)
    img = Image.fromarray(arr, "RGB")

    draw = ImageDraw.Draw(img)
    for i in range(0, width, 60):
        draw.line([(i, 0), (i + height, height)], fill=(255, 255, 255, 5), width=1)
    return img


# ═══════════════════════════════════════════════════════════
# 4. Point d'entrée principal
# ═══════════════════════════════════════════════════════════

def get_image(query: str, article_text: str = "") -> Image.Image:
    """
    Point d'entrée principal.

    Essaie Pexels, puis Unsplash, puis génère un fallback.
    Gemini choisit la meilleure image si `article_text` est fourni.

    Args:
        query:        Requête de recherche (titre anglais de préférence).
        article_text: Texte complet ou description de l'article pour
                      guider Gemini dans le choix de l'image.
    """
    logger.info("Recherche image pour : '%s'", query)

    img = fetch_from_pexels(query, article_text) or fetch_from_unsplash(query, article_text)

    if img is None:
        logger.warning("Aucune image trouvée pour '%s', utilisation du fallback.", query)
        img = _generate_fallback_image()

    return img
