"""
Runs every 30 min via GitHub Actions. For each account inside its active
window, this publishes a burst of up to `posts_per_burst` posts, choosing
whichever queued items have been posted least recently (round-robin). If the
queue has fewer items than the burst size, everything in the queue goes out
every burst — the same posts repeat all day until you add more or remove
some.

24 bursts x 10 posts across a 12h window = 240 posts/day/account.
"""

import json
import os
import sys
import time
from datetime import datetime, timezone

import requests

GRAPH_BASE = "https://graph.threads.net/v1.0"
ACCOUNTS_FILE = "accounts.json"


def load_json(path):
    with open(path) as f:
        return json.load(f)


def save_json(path, data):
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def create_container(user_id, token, text):
    resp = requests.post(
        f"{GRAPH_BASE}/{user_id}/threads",
        data={"media_type": "TEXT", "text": text, "access_token": token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def publish_container(user_id, token, creation_id):
    time.sleep(5)
    resp = requests.post(
        f"{GRAPH_BASE}/{user_id}/threads_publish",
        data={"creation_id": creation_id, "access_token": token},
    )
    resp.raise_for_status()
    return resp.json()["id"]


def in_active_window(account, now):
    start = account.get("active_start_hour_utc", 0)
    end = account.get("active_end_hour_utc", 24)
    return start <= now.hour < end


def publish_one(account, post, token, user_id):
    print(f"[{account['id']}] publishing: {post['text'][:50]}...")
    try:
        creation_id = create_container(user_id, token, post["text"])
        media_id = publish_container(user_id, token, creation_id)
        post["times_posted"] = post.get("times_posted", 0) + 1
        post["last_posted_at"] = datetime.now(timezone.utc).isoformat()
        post["last_media_id"] = media_id
        post.pop("last_error", None)
        print(f"[{account['id']}] -> published, media id {media_id}")
    except requests.HTTPError as e:
        post["last_error"] = e.response.text
        print(f"[{account['id']}] -> FAILED: {e.response.text}", file=sys.stderr)


def process_account(account):
    acc_id = account["id"]
    queue_path = f"queues/{acc_id}.json"
    if not os.path.exists(queue_path):
        print(f"[{acc_id}] no queue file, skipping")
        return False

    now = datetime.now(timezone.utc)
    if not in_active_window(account, now):
        print(f"[{acc_id}] outside active window, skipping")
        return False

    token = os.environ.get(account["token_secret"])
    user_id = os.environ.get(account["user_id_secret"])
    if not token or not user_id:
        print(f"[{acc_id}] missing secrets, skipping", file=sys.stderr)
        return False

    queue = load_json(queue_path)
    if not queue:
        print(f"[{acc_id}] queue empty, nothing to post")
        return False

    # Round-robin: least-recently-posted (or never posted) items go first.
    def sort_key(p):
        times = p.get("times_posted", 0)
        last = p.get("last_posted_at")
        last_sortable = "" if not last else last
        return (times, last_sortable)

    ordered = sorted(queue, key=sort_key)
    burst_size = account.get("posts_per_burst", 10)
    gap = account.get("seconds_between_posts_in_burst", 150)
    batch = ordered[:burst_size]

    for i, post in enumerate(batch):
        publish_one(account, post, token, user_id)
        save_json(queue_path, queue)
        if i < len(batch) - 1:
            time.sleep(gap)

    return True


def main():
    accounts = load_json(ACCOUNTS_FILE)
    any_changed = False
    for account in accounts:
        if process_account(account):
            any_changed = True
    if not any_changed:
        print("No accounts needed action this run.")


if __name__ == "__main__":
    main()
