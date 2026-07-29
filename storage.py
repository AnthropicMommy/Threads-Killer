import os
import json
import uuid
import logging
import requests
from datetime import datetime, timezone

logger = logging.getLogger(__name__)

GIST_ID_QUEUES = os.environ.get("GIST_ID_QUEUES", "")
GIST_ID_COOLDOWNS = os.environ.get("GIST_ID_COOLDOWNS", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
GITHUB_API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _read_gist(gist_id):
    if not gist_id or not GITHUB_TOKEN:
        logger.error("Missing GIST_ID or GITHUB_TOKEN")
        return {}
    try:
        resp = requests.get(f"{GITHUB_API}/gists/{gist_id}", headers=_headers(), timeout=10)
        logger.info(f"Read gist {gist_id}: status={resp.status_code}")
        resp.raise_for_status()
        files = resp.json().get("files", {})
        for fname, fdata in files.items():
            content = fdata.get("content", "{}")
            logger.info(f"  File: {fname}, content length: {len(content)}")
            return json.loads(content)
        return {}
    except Exception as e:
        logger.error(f"Failed to read gist {gist_id}: {e}")
        return {}


def _write_gist(gist_id, filename, data):
    if not gist_id or not GITHUB_TOKEN:
        logger.error("Missing GIST_ID or GITHUB_TOKEN for write")
        return False
    try:
        content = json.dumps(data, indent=2)
        resp = requests.patch(
            f"{GITHUB_API}/gists/{gist_id}",
            headers=_headers(),
            json={"files": {filename: {"content": content}}},
            timeout=10,
        )
        logger.info(f"Write gist {gist_id} file={filename}: status={resp.status_code}")
        resp.raise_for_status()
        return True
    except Exception as e:
        logger.error(f"Failed to write gist {gist_id}: {e}")
        return False


def get_queue(account_id):
    queues = _read_gist(GIST_ID_QUEUES)
    return queues.get(account_id, [])


def save_queue(account_id, posts):
    queues = _read_gist(GIST_ID_QUEUES)
    queues[account_id] = posts
    return _write_gist(GIST_ID_QUEUES, "queues.json", queues)


def add_post(account_id, text):
    posts = get_queue(account_id)
    post_id = uuid.uuid4().hex[:8]
    post = {
        "id": post_id,
        "text": text,
        "added_at": datetime.now(timezone.utc).isoformat(),
        "times_posted": 0,
        "last_posted_at": None,
        "last_media_id": None,
        "last_error": None,
    }
    posts.append(post)
    ok = save_queue(account_id, posts)
    logger.info(f"add_post({account_id}): saved={ok}, total={len(posts)}")
    return post_id


def edit_post(account_id, post_id, new_text):
    posts = get_queue(account_id)
    for p in posts:
        if p["id"] == post_id:
            p["text"] = new_text
            save_queue(account_id, posts)
            return True
    return False


def remove_post(account_id, post_id):
    posts = get_queue(account_id)
    new_posts = [p for p in posts if p["id"] != post_id]
    save_queue(account_id, new_posts)
    return len(new_posts) < len(posts)


def clear_queue(account_id):
    save_queue(account_id, [])


def get_next_post(account_id):
    posts = get_queue(account_id)
    if not posts:
        return None
    posts.sort(key=lambda p: (p.get("times_posted", 0), p.get("last_posted_at") or ""))
    return posts[0]


def update_post_stats(account_id, post_id, media_id=None, error=None):
    posts = get_queue(account_id)
    for p in posts:
        if p["id"] == post_id:
            now = datetime.now(timezone.utc).isoformat()
            if error:
                p["last_error"] = error
                p["last_posted_at"] = now
            else:
                p["times_posted"] = p.get("times_posted", 0) + 1
                p["last_posted_at"] = now
                p["last_media_id"] = media_id
                p["last_error"] = None
            break
    save_queue(account_id, posts)


def get_cooldowns():
    return _read_gist(GIST_ID_COOLDOWNS)


def set_cooldown(account_id, paused):
    cooldowns = get_cooldowns()
    cooldowns[account_id] = paused
    _write_gist(GIST_ID_COOLDOWNS, "gistfile1.txt", cooldowns)


def is_paused(account_id):
    cooldowns = get_cooldowns()
    return cooldowns.get(account_id, False)


def set_cooldown_all(paused):
    from config import ACCOUNT_IDS
    cooldowns = {acc_id: paused for acc_id in ACCOUNT_IDS}
    _write_gist(GIST_ID_COOLDOWNS, "gistfile1.txt", cooldowns)
