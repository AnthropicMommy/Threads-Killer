import time
from datetime import datetime, timezone

from config import ACCOUNTS
from db import is_paused, get_next_posts, update_post_stats
from threads_api import publish_one


def in_active_window(account, now):
    start = account.get("active_start_hour_utc", 0)
    end = account.get("active_end_hour_utc", 24)
    return start <= now.hour < end


def run_scheduled_posting():
    print(f"[scheduler] Running at {datetime.now(timezone.utc).isoformat()}")
    for account in ACCOUNTS:
        acc_id = account["id"]

        if is_paused(acc_id):
            print(f"[{acc_id}] paused (cooldown), skipping")
            continue

        now = datetime.now(timezone.utc)
        if not in_active_window(account, now):
            print(f"[{acc_id}] outside active window ({account['active_start_hour_utc']}-{account['active_end_hour_utc']} UTC), skipping")
            continue

        burst_size = account.get("posts_per_burst", 10)
        gap = account.get("seconds_between_posts_in_burst", 150)
        batch = get_next_posts(acc_id, burst_size)

        if not batch:
            print(f"[{acc_id}] queue empty, nothing to post")
            continue

        print(f"[{acc_id}] posting {len(batch)} posts (burst gap: {gap}s)")

        for i, post in enumerate(batch):
            result = publish_one(acc_id, post)

            if isinstance(result, tuple) and result[0] is None:
                update_post_stats(post["id"], media_id=None, error=result[1])
            else:
                update_post_stats(post["id"], media_id=result)

            if i < len(batch) - 1:
                time.sleep(gap)

    print("[scheduler] Run complete")
