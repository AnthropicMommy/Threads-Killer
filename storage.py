import os
import json
import requests

GIST_ID_QUEUES = os.environ.get("GIST_ID_QUEUES", "")
GIST_ID_COOLDOWNS = os.environ.get("GIST_ID_COOLDOWNS", "")
GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN", "")
QUEUE_FILENAME = "queues.json"
COOLDOWNS_FILENAME = "gistfile1.txt"

GITHUB_API = "https://api.github.com"


def _headers():
    return {
        "Authorization": f"token {GITHUB_TOKEN}",
        "Accept": "application/vnd.github.v3+json",
    }


def _get_gist_id(filename):
    if filename == QUEUE_FILENAME:
        return GIST_ID_QUEUES
    return GIST_ID_COOLDOWNS


def _load_file(filename):
    gist_id = _get_gist_id(filename)
    if not gist_id or not GITHUB_TOKEN:
        return {}
    try:
        resp = requests.get(f"{GITHUB_API}/gists/{gist_id}", headers=_headers())
        resp.raise_for_status()
        files = resp.json().get("files", {})
        for f in files.values():
            return json.loads(f["content"])
        return {}
    except Exception:
        return {}


def _save_file(filename, data):
    gist_id = _get_gist_id(filename)
    if not gist_id or not GITHUB_TOKEN:
        return False
    try:
        target_filename = QUEUE_FILENAME if filename == QUEUE_FILENAME else "gistfile1.txt"
        resp = requests.patch(
            f"{GITHUB_API}/gists/{gist_id}",
            headers=_headers(),
            json={"files": {target_filename: {"content": json.dumps(data, indent=2)}}},
        )
        resp.raise_for_status()
        return True
    except Exception:
        return False


def get_queue(account_id):
    queues = _load_file(QUEUE_FILENAME)
    return queues.get(account_id, [])


def save_queue(account_id, posts):
    queues = _load_file(QUEUE_FILENAME)
    queues[account_id] = posts
    _save_file(QUEUE_FILENAME, queues)


def add_post(account_id, text):
    import uuid
    from datetime import datetime, timezone

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
    save_queue(account_id, posts)
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
    posts = [p for p in posts if p["id"] != post_id]
    save_queue(account_id, posts)
    return True


def get_next_post(account_id):
    posts = get_queue(account_id)
    if not posts:
        return None
    posts.sort(key=lambda p: (p.get("times_posted", 0), p.get("last_posted_at") or ""))
    return posts[0]


def update_post_stats(account_id, post_id, media_id=None, error=None):
    from datetime import datetime, timezone

    posts = get_queue(account_id)
    for p in posts:
        if p["id"] == post_id:
            if error:
                p["last_error"] = error
                p["last_posted_at"] = datetime.now(timezone.utc).isoformat()
            else:
                p["times_posted"] = p.get("times_posted", 0) + 1
                p["last_posted_at"] = datetime.now(timezone.utc).isoformat()
                p["last_media_id"] = media_id
                p["last_error"] = None
            break
    save_queue(account_id, posts)


def get_cooldowns():
    return _load_file(COOLDOWNS_FILENAME)


def set_cooldown(account_id, paused):
    cooldowns = get_cooldowns()
    cooldowns[account_id] = paused
    _save_file(COOLDOWNS_FILENAME, cooldowns)


def is_paused(account_id):
    cooldowns = get_cooldowns()
    return cooldowns.get(account_id, False)


def set_cooldown_all(paused):
    from config import ACCOUNT_IDS
    cooldowns = {}
    for acc_id in ACCOUNT_IDS:
        cooldowns[acc_id] = paused
    _save_file(COOLDOWNS_FILENAME, cooldowns)
