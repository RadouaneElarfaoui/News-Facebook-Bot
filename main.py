"""
Screen Drop Bot — Main Entry Point
==================================
Orchestrateur du pipeline complet (propulsé par Antigravity CLI `agy`) avec support Scheduler.
"""
import argparse
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

# Setup path
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

from modules.content.engine import ContentEngine
from modules.core.config_loader import config
from modules.core.database import (
    article_exists,
    get_metadata,
    increment_consecutive_failures,
    init_db,
    mark_article_posted,
    reset_consecutive_failures,
    save_article,
    save_metadata,
)
from modules.core.logger import get_logger
from modules.llm import LLMAuthError, get_backend
from modules.publisher.fb_api import publish_comment, publish_photo
from modules.radar.aggregator import fetch_trending_news
from modules.visual.compositor import compose_image
from modules.visual.image_fetcher import get_image

logger = get_logger("main")


def _write_alert(reason: str):
    alert_path = BASE_DIR / "data" / "bot.alert"
    alert_path.parent.mkdir(parents=True, exist_ok=True)
    now_iso = datetime.now(timezone.utc).isoformat()
    alert_path.write_text(f"{reason}\nTimestamp: {now_iso}\n", encoding="utf-8")
    logger.info("🔴 Fichier d'alerte écrit dans %s", alert_path)


def _cleanup_old_outputs():
    """Supprime les images générées dans output/ plus vieilles que `keep_output_days`."""
    vis_cfg = config.get("visual", {})
    keep_days = int(vis_cfg.get("keep_output_days", 14))
    if keep_days <= 0:
        return

    out_dir = BASE_DIR / vis_cfg.get("output_dir", "output/")
    if not out_dir.exists():
        return

    cutoff = time.time() - (keep_days * 86400)
    removed = 0
    for f in out_dir.glob("post_*.jpg"):
        try:
            if f.stat().st_mtime < cutoff:
                f.unlink(missing_ok=True)
                removed += 1
        except Exception as e:
            logger.debug("Impossible de supprimer %s : %s", f, e)

    if removed:
        logger.info("🧹 Nettoyage : %d anciennes images supprimées (>%dj).", removed, keep_days)


def _touch_heartbeat(processed_count: int = 0):
    """Met à jour le fichier heartbeat data/bot.alive."""
    now_iso = datetime.now(timezone.utc).isoformat()
    alive_path = BASE_DIR / "data" / "bot.alive"
    alive_path.parent.mkdir(parents=True, exist_ok=True)
    alive_path.write_text(now_iso, encoding="utf-8")
    logger.debug("💓 Heartbeat écrit dans %s (%d articles traités)", alive_path, processed_count)


def _check_publish_staleness():
    """Vérifie si aucune publication réelle n'a eu lieu depuis trop longtemps."""
    pub_cfg = config.get("publisher", {})
    if pub_cfg.get("is_draft", False):
        return

    max_hours = int(pub_cfg.get("alert_no_publish_hours", 24))
    last_pub_str = get_metadata("last_publish")
    if not last_pub_str:
        return

    try:
        last_pub = datetime.fromisoformat(last_pub_str)
        if last_pub.tzinfo is None:
            last_pub = last_pub.replace(tzinfo=timezone.utc)
        hours_since = (datetime.now(timezone.utc) - last_pub).total_seconds() / 3600
        if hours_since > max_hours:
            msg = f"Aucune publication Facebook réussie depuis {int(hours_since)}h (seuil: {max_hours}h)."
            logger.warning("⚠️ %s", msg)
            _write_alert(msg)
    except Exception as e:
        logger.debug("Erreur vérification last_publish : %s", e)


def run_full_pipeline():
    """
    Lance une session de traitement :
    1. Initialise la DB & nettoie les anciens fichiers
    2. Récupère les news GNews
    3. Génère le package éditorial via `agy` (1 appel structuré)
    4. Sélectionne et compose le visuel 1200x630
    5. Publie sur Facebook + 1er commentaire détaillé
    6. Sauvegarde le statut et le heartbeat
    """
    brand_name = config.get("brand", {}).get("name", "Screen Drop")
    pub_cfg = config.get("publisher", {})
    is_draft = bool(pub_cfg.get("is_draft", False))
    max_per_run = int(pub_cfg.get("posts_per_run", 1))

    logger.info(
        "🚀 Démarrage du pipeline %s (max=%d, draft=%s)",
        brand_name,
        max_per_run,
        is_draft,
    )

    init_db()
    _cleanup_old_outputs()
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
                _write_alert(f"Consecutive failures: {fail_count}")
        # Heartbeat systématique même si aucune news fraîche n'est disponible
        _touch_heartbeat()
        return

    engine = ContentEngine()
    processed_count = 0

    for art in articles:
        url = art.get("url")
        if not url or article_exists(url):
            continue

        logger.info("--- Nouveau sujet : %s ---", art.get("title"))
        source_text = art.get("description") or art.get("title")

        # 2. Génération du package complet en un seul appel agy
        try:
            pkg = engine.generate_package(source_text)
        except LLMAuthError as auth_err:
            logger.critical("🚨 Session agy expirée ou non connectée : %s", auth_err)
            _write_alert(
                "agy: session expirée ou non connectée — lancez 'python main.py --agy-login'"
            )
            pipeline_error = True
            break

        if not pkg:
            logger.warning("Sujet ignoré : échec de génération du package éditorial.")
            pipeline_error = True
            continue

        title = pkg["title"]
        keywords = pkg["keywords"]
        search_query = pkg["image_query"]
        caption = pkg["caption"]
        detail_comment = pkg["detail_comment"]

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
                output_filename=output_filename,
            )

            # 5. PUBLICATION FACEBOOK
            fb_post_id = publish_photo(final_path, caption)

            if fb_post_id:
                if detail_comment:
                    publish_comment(fb_post_id, detail_comment)

                if not is_draft:
                    # 6. Sauvegarde BDD SEULEMENT EN PRODUCTION APRÈS SUCCÈS FB
                    article_id = save_article(url, title, "news", art.get("image", ""))
                    mark_article_posted(
                        article_id=article_id,
                        fb_post_id=fb_post_id,
                        image_path=str(final_path),
                        caption=caption,
                    )
                    save_metadata("last_publish", datetime.now(timezone.utc).isoformat())
                    logger.info("✅ Pipeline réussi et publié ! ID FB: %s", fb_post_id)
                else:
                    logger.info(
                        "✅ [MODE DRAFT] Run validé sans écriture BDD ! Image: %s",
                        final_path,
                    )

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
        alert_file = BASE_DIR / "data" / "bot.alert"
        if alert_file.exists():
            alert_file.unlink(missing_ok=True)
    elif pipeline_error:
        fail_count = increment_consecutive_failures()
        logger.warning("⚠️ Échec #%d consécutif du pipeline.", fail_count)
        if fail_count >= 3:
            logger.critical("🚨 %d échecs consécutifs ! Le bot est peut-être en panne.", fail_count)
            _write_alert(f"Consecutive failures: {fail_count}")

    _check_publish_staleness()

    now_iso = datetime.now(timezone.utc).isoformat()
    save_metadata("last_run", now_iso)
    save_metadata("last_successful_run", now_iso)  # rétrocompatibilité

    _touch_heartbeat(processed_count)


def start_scheduler():
    """
    Lance le scheduler pour exécuter le pipeline aux heures configurées.
    """
    from apscheduler.schedulers.blocking import BlockingScheduler
    from apscheduler.triggers.cron import CronTrigger
    from apscheduler.triggers.interval import IntervalTrigger

    init_db()
    # Heartbeat immédiat au démarrage du scheduler
    _touch_heartbeat(0)

    scheduler = BlockingScheduler()
    # Tâche de heartbeat périodique toutes les 10 minutes (évite faux positifs healthcheck la nuit)
    scheduler.add_job(
        lambda: _touch_heartbeat(0),
        IntervalTrigger(minutes=10),
        name="ScreenDrop_Heartbeat",
    )

    posting_hours = config.get("publisher", {}).get("posting_hours", [8, 12, 18])
    hours_str = ",".join(map(str, posting_hours))

    # Rattrapage des runs manqués
    last_run_str = get_metadata("last_run") or get_metadata("last_successful_run")
    if last_run_str:
        try:
            last_run = datetime.fromisoformat(last_run_str)
            if last_run.tzinfo is None:
                last_run = last_run.replace(tzinfo=timezone.utc)
            hours_since = (datetime.now(timezone.utc) - last_run).total_seconds() / 3600
            interval_hours = (
                min(b - a for a, b in zip(posting_hours, posting_hours[1:]))
                if len(posting_hours) > 1
                else 2
            )

            if hours_since > interval_hours * 1.5:
                catch_up_count = min(int(hours_since / interval_hours), 3)
                logger.info(
                    "🔁 Rattrapage : %d runs manqués détectés (%dh sans activité).",
                    catch_up_count,
                    int(hours_since),
                )
                for i in range(catch_up_count):
                    logger.info("🔁 Run de rattrapage %d/%d", i + 1, catch_up_count)
                    run_full_pipeline()
                    time.sleep(30)
        except Exception as e:
            logger.error("Erreur lors du calcul du rattrapage : %s", e)
    else:
        logger.info("🆕 Premier démarrage détecté, pas de rattrapage.")

    trigger = CronTrigger(hour=hours_str, minute=0)
    scheduler.add_job(run_full_pipeline, trigger, name="ScreenDrop_Pipeline")

    logger.info("📅 Scheduler démarré. Heures de publication : %s", hours_str)

    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("👋 Scheduler arrêté.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Screen Drop Bot")
    parser.add_argument("--schedule", action="store_true", help="Lancer en mode scheduler (daemon)")
    parser.add_argument("--once", action="store_true", help="Lancer une seule fois immédiatement")
    parser.add_argument(
        "--agy-login",
        action="store_true",
        help="Lancer agy en mode interactif pour connecter le compte Google AI Pro",
    )
    parser.add_argument(
        "--agy-check",
        action="store_true",
        help="Tester rapidement la connexion et la réponse structurée de agy",
    )

    args = parser.parse_args()

    if args.agy_login:
        sys.exit(get_backend().run_interactive_login())
    elif args.agy_check:
        ok, info = get_backend().check_health()
        if ok:
            print(f"✅ agy opérationnel : {info}")
            sys.exit(0)
        else:
            print(f"❌ Échec agy : {info}")
            sys.exit(1)
    elif args.schedule:
        start_scheduler()
    elif args.once:
        run_full_pipeline()
    else:
        run_full_pipeline()
