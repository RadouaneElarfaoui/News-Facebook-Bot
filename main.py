"""
Screen Mix Bot — Main Entry Point
=================================
Orchestrateur du pipeline complet avec support Scheduler.
"""
import sys
import time
import argparse
from pathlib import Path
from datetime import datetime, timezone

# Setup path
sys.path.insert(0, str(Path(__file__).resolve().parent))

from modules.core.config_loader import config
from modules.core.logger import get_logger
from modules.core.database import (
    init_db, article_exists, save_article, mark_article_posted,
    save_metadata, get_metadata, increment_consecutive_failures, reset_consecutive_failures
)
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
    pipeline_error = False
    
    # 1. Collecte
    try:
        articles = fetch_trending_news()
    except Exception as e:
        logger.error("Erreur récupération des news : %s", e)
        articles = None
        pipeline_error = True

    if not articles:
        logger.warning("Fin du pipeline : aucune news à traiter.")
        if pipeline_error:
            fail_count = increment_consecutive_failures()
            logger.warning("⚠️ Échec #%d consécutif du pipeline.", fail_count)
            if fail_count >= 3:
                logger.critical("🚨 %d échecs consécutifs ! Le bot est peut-être en panne.", fail_count)
                alert_path = Path(__file__).resolve().parent / "data" / "bot.alert"
                alert_path.write_text(f"Consecutive failures: {fail_count}\nLast: {datetime.now(timezone.utc).isoformat()}")
                logger.info("🔴 Fichier d'alerte écrit dans %s", alert_path)
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
            
            # 5. PUBLICATION FACEBOOK
            fb_post_id = publish_photo(final_path, caption)
            
            if fb_post_id:
                # 6. Sauvegarde BDD SEULEMENT APRÈS SUCCÈS FB
                article_id = save_article(url, title, "news", art.get("image", ""))
                
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
                processed_count += 1
            else:
                logger.warning("⚠️ Image générée mais échec de publication Facebook.")
                pipeline_error = True
            
            if processed_count >= max_per_run:
                break
                
        except Exception as e:
            logger.error("Erreur critique dans le pipeline : %s", e)
            pipeline_error = True

    if processed_count > 0:
        reset_consecutive_failures()
    elif pipeline_error:
        fail_count = increment_consecutive_failures()
        logger.warning("⚠️ Échec #%d consécutif du pipeline.", fail_count)
        if fail_count >= 3:
            logger.critical("🚨 %d échecs consécutifs ! Le bot est peut-être en panne.", fail_count)
            alert_path = Path(__file__).resolve().parent / "data" / "bot.alert"
            alert_path.write_text(f"Consecutive failures: {fail_count}\nLast: {datetime.now(timezone.utc).isoformat()}")
            logger.info("🔴 Fichier d'alerte écrit dans %s", alert_path)

    logger.info("🏁 Pipeline terminé. %d articles traités.", processed_count)
    save_metadata("last_successful_run", datetime.now(timezone.utc).isoformat())

    # Heartbeat fichier .alive
    alive_path = Path(__file__).resolve().parent / "data" / "bot.alive"
    alive_path.write_text(datetime.now(timezone.utc).isoformat())
    logger.info("💓 Heartbeat écrit dans %s", alive_path)


def start_scheduler():
    """
    Lance le scheduler pour exécuter le pipeline aux heures configurées.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger

    init_db()
    scheduler = BlockingScheduler()
    posting_hours = config.get("publisher", {}).get("posting_hours", [8, 12, 18])
    
    # On convertit la liste d'heures en format cron (ex: "8,12,18")
    hours_str = ",".join(map(str, posting_hours))
    
    # Rattrapage des runs manqués
    last_run_str = get_metadata("last_successful_run")
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str)
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - last_run).total_seconds() / 3600
            interval_hours = min(b - a for a, b in zip(posting_hours, posting_hours[1:])) if len(posting_hours) > 1 else 2

            if hours_since > interval_hours * 1.5:
                catch_up_count = min(int(hours_since / interval_hours), 3)
                logger.info("🔁 Rattrapage : %d runs manqués détectés (%dh sans activité).", catch_up_count, int(hours_since))
                for i in range(catch_up_count):
                    logger.info("🔁 Run de rattrapage %d/%d", i + 1, catch_up_count)
                    run_full_pipeline()
                    time.sleep(30)
        except Exception as e:
            logger.error("Erreur lors du calcul du rattrapage : %s", e)
    else:
        logger.info("🆕 Premier démarrage détecté, pas de rattrapage.")

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
