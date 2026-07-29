import sqlite3
import uuid
from datetime import datetime, timezone

from config import DATABASE_PATH, ACCOUNT_IDS


def get_conn():
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    conn = get_conn()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS posts (
            id TEXT PRIMARY KEY,
            account_id TEXT NOT NULL,
            text TEXT NOT NULL,
            added_at TEXT NOT NULL,
            times_posted INTEGER DEFAULT 0,
            last_posted_at TEXT,
            last_media_id TEXT,
            last_error TEXT
        );
        CREATE TABLE IF NOT EXISTS cooldowns (
            account_id TEXT PRIMARY KEY,
            is_paused INTEGER DEFAULT 0,
            paused_at TEXT
        );
    """)
    for acc_id in ACCOUNT_IDS:
        conn.execute(
            "INSERT OR IGNORE INTO cooldowns (account_id, is_paused) VALUES (?, 0)",
            (acc_id,),
        )
    conn.commit()
    conn.close()


def add_post(account_id, text):
    post_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    conn = get_conn()
    conn.execute(
        "INSERT INTO posts (id, account_id, text, added_at) VALUES (?, ?, ?, ?)",
        (post_id, account_id, text, now),
    )
    conn.commit()
    conn.close()
    return post_id


def edit_post(account_id, post_id, new_text):
    conn = get_conn()
    cur = conn.execute(
        "UPDATE posts SET text = ? WHERE id = ? AND account_id = ?",
        (new_text, post_id, account_id),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0


def remove_post(account_id, post_id):
    conn = get_conn()
    cur = conn.execute(
        "DELETE FROM posts WHERE id = ? AND account_id = ?",
        (post_id, account_id),
    )
    conn.commit()
    changed = cur.rowcount
    conn.close()
    return changed > 0


def get_queue(account_id):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM posts WHERE account_id = ? ORDER BY times_posted ASC, last_posted_at ASC",
        (account_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_next_posts(account_id, count):
    conn = get_conn()
    rows = conn.execute(
        "SELECT * FROM posts WHERE account_id = ? ORDER BY times_posted ASC, last_posted_at ASC LIMIT ?",
        (account_id, count),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def update_post_stats(post_id, media_id, error=None):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat()
    if error:
        conn.execute(
            "UPDATE posts SET last_error = ?, last_posted_at = ? WHERE id = ?",
            (error, now, post_id),
        )
    else:
        conn.execute(
            """UPDATE posts SET
                times_posted = times_posted + 1,
                last_posted_at = ?,
                last_media_id = ?,
                last_error = NULL
            WHERE id = ?""",
            (now, media_id, post_id),
        )
    conn.commit()
    conn.close()


def set_cooldown(account_id, paused):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat() if paused else None
    conn.execute(
        "UPDATE cooldowns SET is_paused = ?, paused_at = ? WHERE account_id = ?",
        (1 if paused else 0, now, account_id),
    )
    conn.commit()
    conn.close()


def set_cooldown_all(paused):
    conn = get_conn()
    now = datetime.now(timezone.utc).isoformat() if paused else None
    conn.execute(
        "UPDATE cooldowns SET is_paused = ?, paused_at = ?",
        (1 if paused else 0, now),
    )
    conn.commit()
    conn.close()


def is_paused(account_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT is_paused FROM cooldowns WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    conn.close()
    return row and row["is_paused"] == 1


def get_cooldown_state(account_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT * FROM cooldowns WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_queue_size(account_id):
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM posts WHERE account_id = ?",
        (account_id,),
    ).fetchone()
    conn.close()
    return row["cnt"]


def get_posts_today(account_id):
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    conn = get_conn()
    row = conn.execute(
        "SELECT COUNT(*) as cnt FROM posts WHERE account_id = ? AND last_posted_at LIKE ?",
        (account_id, f"{today}%"),
    ).fetchone()
    conn.close()
    return row["cnt"]
