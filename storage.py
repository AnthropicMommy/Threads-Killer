import os
import re
import uuid
import logging
import json
import psycopg2
import requests
from datetime import datetime, timezone, timedelta
from html import unescape

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
        cur.execute("""
            CREATE TABLE IF NOT EXISTS x_sources (
                id TEXT PRIMARY KEY,
                username TEXT NOT NULL UNIQUE,
                added_at TEXT NOT NULL
            )
        """)
        cur.execute("""
            CREATE TABLE IF NOT EXISTS x_posted (
                tweet_id TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                posted_at TEXT NOT NULL
            )
        """)
        cur.execute("INSERT INTO cooldowns (account_id, is_paused) VALUES ('acc1', 0) ON CONFLICT DO NOTHING")
        logger.info("Database initialized")
    except Exception as e:
        logger.error(f"init_db failed: {e}")


# --- Post management ---

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


# --- X Source management ---

def add_source(username):
    username = username.lstrip("@").strip().split("/")[-1]
    source_id = uuid.uuid4().hex[:8]
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO x_sources (id, username, added_at) VALUES (%s, %s, %s) ON CONFLICT (username) DO NOTHING",
            (source_id, username, now),
        )
        return True
    except Exception as e:
        logger.error(f"add_source failed: {e}")
        return False


def remove_source(username):
    username = username.lstrip("@").strip()
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("DELETE FROM x_sources WHERE username = %s", (username,))
        return cur.rowcount > 0
    except Exception as e:
        logger.error(f"remove_source failed: {e}")
        return False


def get_sources():
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT username FROM x_sources ORDER BY added_at ASC")
        return [row[0] for row in cur.fetchall()]
    except Exception as e:
        logger.error(f"get_sources failed: {e}")
        return []


def was_tweet_posted(tweet_id):
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute("SELECT 1 FROM x_posted WHERE tweet_id = %s", (tweet_id,))
        return cur.fetchone() is not None
    except Exception as e:
        logger.error(f"was_tweet_posted failed: {e}")
        return False


def mark_tweet_posted(tweet_id, username):
    now = datetime.now(timezone.utc).isoformat()
    try:
        conn = _get_conn()
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO x_posted (tweet_id, username, posted_at) VALUES (%s, %s, %s) ON CONFLICT DO NOTHING",
            (tweet_id, username, now),
        )
    except Exception as e:
        logger.error(f"mark_tweet_posted failed: {e}")


# --- X Scraper ---
    try:
        resp = requests.get(
            f"https://syndication.twitter.com/srv/timeline-profile/screen-name/{username}",
            headers={"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"},
            timeout=15,
        )
        if resp.status_code != 200:
            logger.warning(f"Syndication returned {resp.status_code} for @{username}")
            return []

        import re
        match = re.search(r'__NEXT_DATA__[^>]*>(.*?)</script>', resp.text)
        if not match:
            logger.warning(f"No data found for @{username}")
            return []

        data = json.loads(match.group(1))
        entries = data.get("props", {}).get("pageProps", {}).get("timeline", {}).get("entries", [])

        one_hour_ago = datetime.now(timezone.utc) - timedelta(hours=1)
        results = []
        for entry in entries:
            content = entry.get("content", {})
            tweet = content.get("tweet", {})
            tweet_id = tweet.get("id_str", entry.get("sortIndex", "").split("/")[-1])
            text = tweet.get("full_text", tweet.get("text", ""))
            created = tweet.get("created_at", "")

            if created:
                try:
                    pub_dt = datetime.strptime(created, "%a %b %d %H:%M:%S %z %Z")
                    if pub_dt.replace(tzinfo=timezone.utc) < one_hour_ago:
                        continue
                except Exception:
                    pass

            text = re.sub(r'https?://\S+', '', text).strip()
            text = unescape(text)

            if text and tweet_id and not was_tweet_posted(tweet_id):
                results.append({
                    "id": tweet_id,
                    "username": username,
                    "text": text,
                })

        return results
    except Exception as e:
        logger.error(f"fetch_tweets_from_x failed for @{username}: {e}")
        return []


def scan_and_queue(account_id="acc1"):
    sources = get_sources()
    if not sources:
        return "No X sources."

    results = []
    total_new = 0
    for username in sources:
        tweets = fetch_tweets_from_x(username)
        for tweet in tweets:
            add_post(account_id, tweet["text"])
            mark_tweet_posted(tweet["id"], username)
            total_new += 1
        if tweets:
            results.append(f"@{username}: {len(tweets)} new")
        else:
            results.append(f"@{username}: none")

    return f"Found {total_new} new.\n" + "\n".join(results)
