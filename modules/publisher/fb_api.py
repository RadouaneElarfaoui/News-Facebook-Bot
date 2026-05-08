"""
Publisher — Facebook API
========================
Gère la publication automatique sur Facebook via Graph API.
"""
import httpx
from pathlib import Path
from modules.core.config_loader import config
from modules.core.logger import get_logger

logger = get_logger(__name__)

def publish_photo(image_path: str | Path, caption: str) -> str | None:
    """
    Publie une photo avec une légende sur la page Facebook configurée.
    
    Args:
        image_path: Chemin vers le fichier image local.
        caption: Texte de la publication (légende).
        
    Returns:
        ID du post Facebook en cas de succès, None sinon.
    """
    fb_cfg = config["apis"]["facebook"]
    page_id = fb_cfg["page_id"]
    token = fb_cfg["access_token"]
    api_ver = fb_cfg.get("api_version", "v19.0")
    
    # Si on est en mode draft, on ne publie pas réellement
    if config.get("publisher", {}).get("is_draft", False):
        logger.info("🕒 [MODE DRAFT] Simulation de publication sur Facebook.")
        logger.info("Légende : %s", caption[:100] + "...")
        return "draft_post_id"

    url = f"https://graph.facebook.com/{api_ver}/{page_id}/photos"
    
    # On ouvre le fichier image
    path = Path(image_path)
    if not path.exists():
        logger.error("Fichier image introuvable pour publication : %s", image_path)
        return None

    try:
        logger.info("Envoi de la photo vers Facebook (%s)...", page_id)
        
        with open(path, "rb") as img_file:
            files = {
                "source": img_file
            }
            data = {
                "message": caption,
                "access_token": token
            }
            
            # Utilisation de httpx pour l'envoi
            # Note: Le timeout est augmenté car l'upload peut être lent
            resp = httpx.post(url, data=data, files=files, timeout=60)
            
        if resp.status_code == 200:
            post_id = resp.json().get("id")
            logger.info("✅ Post Facebook réussi ! ID: %s", post_id)
            return post_id
        else:
            logger.error("❌ Échec publication Facebook : %d - %s", resp.status_code, resp.text)
            return None
            
    except Exception as e:
        logger.error("Erreur lors de la publication Facebook : %s", e)
        return None

def publish_comment(post_id: str, message: str) -> str | None:
    """
    Publie un commentaire sur un post Facebook existant.
    """
    fb_cfg = config["apis"]["facebook"]
    token = fb_cfg["access_token"]
    api_ver = fb_cfg.get("api_version", "v19.0")
    
    if config.get("publisher", {}).get("is_draft", False):
        logger.info("🕒 [MODE DRAFT] Simulation de commentaire sur le post %s.", post_id)
        return "draft_comment_id"

    url = f"https://graph.facebook.com/{api_ver}/{post_id}/comments"
    data = {
        "message": message,
        "access_token": token
    }

    try:
        logger.info("Envoi du commentaire sur le post %s...", post_id)
        resp = httpx.post(url, data=data, timeout=30)
        
        if resp.status_code == 200:
            comment_id = resp.json().get("id")
            logger.info("✅ Commentaire réussi ! ID: %s", comment_id)
            return comment_id
        else:
            logger.error("❌ Échec commentaire Facebook : %d - %s", resp.status_code, resp.text)
            return None
    except Exception as e:
        logger.error("Erreur lors du commentaire Facebook : %s", e)
        return None

