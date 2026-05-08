"""
Screen Mix Bot — Main Entry Point
=================================
Orchestrateur du pipeline complet avec support Scheduler.
"""
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.core.config_loader import config
from modules.core.logger import get_logger
from modules.core.database import init_db, article_exists, save_article, mark_article_posted
from modules.radar.aggregator import fetch_trending_news
from modules.content.engine import ContentEngine
from modules.visual.image_fetcher import get_image
from modules.visual.compositor import compose_image
from modules.publisher.fb_api import publish_photo, publish_comment

logger = get_logger("main")

def run_full_pipeline():
    """
    Lance une session de traitement :
    1. Initialise la DB
    2. Récupère les news GNews
    3. Traite chaque article (IA + Visuel)
    4. Publie sur Facebook
    5. Ajoute un commentaire détaillé
    6. Sauvegarde le statut
    """
    brand_name = config.get("brand_name", "News Bot")
    logger.info(f"🚀 Démarrage du pipeline {brand_name}")

    init_db()
    
    # 1. Collecte
    articles = fetch_trending_news()
    if not articles:
        logger.warning("Fin du pipeline : aucune news à traiter.")
        return

    engine = ContentEngine()
    processed_count = 0
    # Limite par session définie en config
    max_per_run = config.get("radar", {}).get("max_articles_per_run", 1)

    for art in articles:
        url = art.get("url")
        if not url or article_exists(url):
            continue
        
        logger.info("--- Nouveau sujet : %s ---", art.get("title"))
        
        # 2. Génération de contenu (Titre + Keywords)
        source_text = art.get("description") or art.get("title")
        post_data = engine.generate_post_data(source_text)
        
        if not post_data or "title" not in post_data:
            logger.warning("Sujet ignoré : échec de génération de contenu.")
            continue
            
        title = post_data["title"]
        keywords = post_data.get("keywords", [])
        search_query = post_data.get("image_query", "breaking news")
        
        # Légende Facebook
        caption = engine.generate_caption(title)
        detail_comment = engine.generate_detail_comment(source_text)
        
        # 3. Récupération d'image
        bg_image = get_image(search_query, article_text=source_text)
        
        # 4. Composition de l'image finale
        timestamp = int(time.time())
        output_filename = f"post_{timestamp}.jpg"
        
        try:
            final_path = compose_image(
                background=bg_image,
                title=title,
                keywords=keywords,
                output_filename=output_filename
            )
            
            # 5. Sauvegarde initiale en DB
            article_id = save_article(url, title, "news", art.get("image", ""))
            
            # 6. PUBLICATION FACEBOOK
            fb_post_id = publish_photo(final_path, caption)
            
            if fb_post_id:
                # 7. PUBLICATION COMMENTAIRE DÉTAILLÉ
                if detail_comment:
                    publish_comment(fb_post_id, detail_comment)

                # 8. Marquage comme publié
                mark_article_posted(
                    article_id=article_id,
                    fb_post_id=fb_post_id,
                    image_path=str(final_path),
                    caption=caption
                )
                logger.info("✅ Pipeline réussi et publié ! ID FB: %s", fb_post_id)
            else:
                logger.warning("⚠️ Image générée mais échec de publication Facebook.")
            
            processed_count += 1
            if processed_count >= max_per_run:
                break
                
        except Exception as e:
            logger.error("Erreur critique dans le pipeline : %s", e)

    logger.info("🏁 Pipeline terminé. %d articles traités.", processed_count)


def start_scheduler():
    """
    Lance le scheduler pour exécuter le pipeline aux heures configurées.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    scheduler = BlockingScheduler()
    posting_hours = config.get("publisher", {}).get("posting_hours", [8, 12, 18])
    
    # On convertit la liste d'heures en format cron (ex: "8,12,18")
    hours_str = ",".join(map(str, posting_hours))
    
    trigger = CronTrigger(hour=hours_str, minute=0)
    scheduler.add_job(run_full_pipeline, trigger, name="ScreenMix_Pipeline")
    
    logger.info("📅 Scheduler démarré. Heures de publication : %s", hours_str)
    
    # Exécution immédiate au démarrage si besoin (optionnel)
    # run_full_pipeline()
    
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Scheduler arrêté.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screen Mix Bot")
    parser.add_argument("--schedule", action="store_true", help="Lancer en mode scheduler (daemon)")
    parser.add_argument("--once", action="store_true", help="Lancer une seule fois immédiatement")
    
    args = parser.parse_args()
    
    if args.schedule:
        start_scheduler()
    elif args.once:
        run_full_pipeline()
    else:
        # Par défaut, on lance une fois si aucun argument n'est fourni
        run_full_pipeline()
