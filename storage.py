import os
import uuid
import logging
import psycopg2
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

DATABASE_URL = os.environ.get("DATABASE_URL", "")

_conn = None


def _get_conn():
    global _conn
    if _conn is None or _conn.closed:
        _conn = psycopg2.connect(DATABASE_URL)
        _conn.autocommit = True
    return _conn


def init_db():
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("""
            CREATE TABLE IF NOT EXISTS posts (
                id TEXT PRIMARY KEY,
                account_id TEXT NOT NULL,
                text TEXT NOT NULL,
                added_at TEXT NOT NULL,
                times_posted INTEGER DEFAULT 0,
                last_posted_at TEXT,
                last_media_id TEXT,
                last_error TEXT
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS cooldowns (
                account_id TEXT PRIMARY KEY,
                is_paused INTEGER DEFAULT 0
            )
        """)
        cur.execute("INSERT INTO cooldowns (account_id, is_paused) VALUES ('acc1', 0) ON CONFLICT DO NOTHING")
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"init_db failed: {e}")


def add_post(account_id, text):
    post_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO posts (id, account_id, text, added_at) VALUES (%s, %s, %s, %s)",
            (post_id, account_id, text, now),
        )
        logger.info(f"add_post({account_id}): id={post_id}")
        return post_id
    except Exception as e:
        logger.error(f"add_post failed: {e}")
        return post_id


def get_queue(account_id):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "SELECT id, text, times_posted, last_posted_at, last_media_id, last_error, added_at FROM posts WHERE account_id = %s ORDER BY times_posted ASC, last_posted_at ASC",
            (account_id,),
        )
        rows = cur.fetchall()
        return [
            {"id": r[0], "text": r[1], "times_posted": r[2], "last_posted_at": r[3], "last_media_id": r[4], "last_error": r[5], "added_at": r[6]}
            for r in rows
        ]
    except Exception as e:
        logger.error(f"get_queue failed: {e}")
        return []


def get_next_post(account_id):
    posts = get_queue(account_id)
    return posts[0] if posts else None


def edit_post(account_id, post_id, new_text):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE posts SET text = %s WHERE id = %s AND account_id = %s", (new_text, post_id, account_id))
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"edit_post failed: {e}")
        return False


def remove_post(account_id, post_id):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE id = %s AND account_id = %s", (post_id, account_id))
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"remove_post failed: {e}")
        return False


def clear_queue(account_id):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM posts WHERE account_id = %s", (account_id,))
    except Exception as e:
        logger.error(f"clear_queue failed: {e}")


def update_post_stats(account_id, post_id, media_id=None, error=None):
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        cur = conn.cursor()
        if error:
            cur.execute("UPDATE posts SET last_error = %s, last_posted_at = %s WHERE id = %s", (error, now, post_id))
        else:
            cur.execute(
                "UPDATE posts SET times_posted = times_posted + 1, last_posted_at = %s, last_media_id = %s, last_error = NULL WHERE id = %s",
                (now, media_id, post_id),
            )
    except Exception as e:
        logger.error(f"update_post_stats failed: {e}")


def is_paused(account_id):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT is_paused FROM cooldowns WHERE account_id = %s", (account_id,))
        row = cur.fetchone()
        return row and row[0] == 1
    except Exception as e:
        logger.error(f"is_paused failed: {e}")
        return False


def set_cooldown(account_id, paused):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE cooldowns SET is_paused = %s WHERE account_id = %s", (1 if paused else 0, account_id))
    except Exception as e:
        logger.error(f"set_cooldown failed: {e}")


def set_cooldown_all(paused):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("UPDATE cooldowns SET is_paused = %s", (1 if paused else 0,))
    except Exception as e:
        logger.error(f"set_cooldown_all failed: {e}")
