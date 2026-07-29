"""
Runs every 30 min via GitHub Actions, triggered on a cron. On each trigger,
for every account that's currently inside its active posting window, this
publishes up to `posts_per_burst` pending posts (FIFO), sleeping
`seconds_between_posts_in_burst` between each one so they don't land in the
same instant. With 10 posts / 150s gaps that's ~22.5 min per burst, safely
inside the 30-min window before the next trigger.

24 bursts x 10 posts across a 12h window = 240 posts/day/account, just under
Threads' 250/24h API limit.
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
    time.sleep(5)  # Threads needs a moment between container creation and publish
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
        post["posted"] = True
        post["posted_at"] = datetime.now(timezone.utc).isoformat()
        post["media_id"] = media_id
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
        print(f"[{acc_id}] outside active window ({account.get('active_start_hour_utc',0)}-{account.get('active_end_hour_utc',24)}h UTC), skipping")
        return False

    token = os.environ.get(account["token_secret"])
    user_id = os.environ.get(account["user_id_secret"])
    if not token or not user_id:
        print(f"[{acc_id}] missing secrets {account['token_secret']} / {account['user_id_secret']}", file=sys.stderr)
        return False

    queue = load_json(queue_path)
    pending = [p for p in queue if not p.get("posted")]
    if not pending:
        print(f"[{acc_id}] queue empty, nothing to post")
        return False

    burst_size = account.get("posts_per_burst", 10)
    gap = account.get("seconds_between_posts_in_burst", 150)
    batch = pending[:burst_size]

    for i, post in enumerate(batch):
        publish_one(account, post, token, user_id)
        save_json(queue_path, queue)  # save after every post so partial progress isn't lost
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
