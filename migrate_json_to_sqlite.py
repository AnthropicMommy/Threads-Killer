import json
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from config import ACCOUNT_IDS
from db import init_db, add_post, get_queue


def migrate():
    init_db()
    for acc_id in ACCOUNT_IDS:
        queue_path = f"queues/{acc_id}.json"
        if not os.path.exists(queue_path):
            print(f"[{acc_id}] no queue file, skipping")
            continue

        with open(queue_path) as f:
            posts = json.load(f)

        if not posts:
            print(f"[{acc_id}] queue empty, skipping")
            continue

        existing = get_queue(acc_id)
        existing_ids = {p["id"] for p in existing}

        migrated = 0
        for post in posts:
            if post["id"] in existing_ids:
                print(f"[{acc_id}] post {post['id']} already exists, skipping")
                continue
            post_id = add_post(acc_id, post["text"])
            migrated += 1
            print(f"[{acc_id}] migrated post {post['id']} -> {post_id}")

        print(f"[{acc_id}] migrated {migrated} posts")


if __name__ == "__main__":
    migrate()
