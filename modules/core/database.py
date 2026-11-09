"""
Core — Database
Gestion SQLite : articles vus, posts publiés, historique.
"""
import sqlite3
from pathlib import Path
from datetime import datetime, timezone

from modules.core.logger import get_logger

logger = get_logger(__name__)
DB_PATH = Path(__file__).resolve().parent.parent.parent / "data" / "bot_data.db"
DB_PATH.parent.mkdir(exist_ok=True)


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA foreign_keys=ON;")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    """Crée les tables si elles n'existent pas."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS articles (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                url         TEXT UNIQUE NOT NULL,
                title_ar    TEXT,
                category    TEXT,
                image_url   TEXT,
                processed   INTEGER DEFAULT 0,
                posted      INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS posts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                article_id  INTEGER REFERENCES articles(id),
                fb_post_id  TEXT,
                image_path  TEXT,
                caption     TEXT,
                scheduled_at TEXT,
                posted_at   TEXT,
                status      TEXT DEFAULT 'pending'
            );

            CREATE TABLE IF NOT EXISTS metadata (
                key   TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
        """)
    logger.info("Database initialized at %s", DB_PATH)


def article_exists(url: str) -> bool:
    with get_connection() as conn:
        row = conn.execute("SELECT 1 FROM articles WHERE url = ?", (url,)).fetchone()
        return row is not None


def save_article(url: str, title_ar: str, category: str, image_url: str) -> int:
    with get_connection() as conn:
        cur = conn.execute(
            "INSERT OR IGNORE INTO articles (url, title_ar, category, image_url) VALUES (?, ?, ?, ?)",
            (url, title_ar, category, image_url),
        )
        conn.commit()
        return cur.lastrowid


def save_metadata(key: str, value: str):
    """Sauvegarde une paire clé/valeur dans metadata."""
    with get_connection() as conn:
        conn.execute(
            "INSERT OR REPLACE INTO metadata (key, value) VALUES (?, ?)",
            (key, value)
        )
        conn.commit()


def get_metadata(key: str) -> str | None:
    """Récupère une valeur par sa clé."""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT value FROM metadata WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def increment_consecutive_failures() -> int:
    """Incrémente le compteur d'échecs consécutifs et retourne la nouvelle valeur."""
    current = get_metadata("consecutive_failures")
    count = (int(current) if current else 0) + 1
    save_metadata("consecutive_failures", str(count))
    return count


def reset_consecutive_failures():
    """Remet le compteur d'échecs à zéro."""
    save_metadata("consecutive_failures", "0")


def mark_article_posted(article_id: int, fb_post_id: str, image_path: str, caption: str):
    now = datetime.now(timezone.utc).isoformat()
    with get_connection() as conn:
        conn.execute("UPDATE articles SET posted = 1 WHERE id = ?", (article_id,))
        conn.execute(
            "INSERT INTO posts (article_id, fb_post_id, image_path, caption, posted_at, status) "
            "VALUES (?, ?, ?, ?, ?, 'published')",
            (article_id, fb_post_id, image_path, caption, now),
        )
        conn.commit()
