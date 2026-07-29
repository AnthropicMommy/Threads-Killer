import os

TELEGRAM_BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]

ACCOUNTS = [
    {
        "id": "acc1",
        "label": "Account 1",
        "token_env": "THREADS_ACCESS_TOKEN_ACC1",
        "user_id_env": "THREADS_USER_ID_ACC1",
        "posts_per_burst": 10,
        "seconds_between_posts_in_burst": 150,
        "active_start_hour_utc": 5,
        "active_end_hour_utc": 17,
    },
    {
        "id": "acc2",
        "label": "Account 2",
        "token_env": "THREADS_ACCESS_TOKEN_ACC2",
        "user_id_env": "THREADS_USER_ID_ACC2",
        "posts_per_burst": 10,
        "seconds_between_posts_in_burst": 150,
        "active_start_hour_utc": 8,
        "active_end_hour_utc": 20,
    },
    {
        "id": "acc3",
        "label": "Account 3",
        "token_env": "THREADS_ACCESS_TOKEN_ACC3",
        "user_id_env": "THREADS_USER_ID_ACC3",
        "posts_per_burst": 10,
        "seconds_between_posts_in_burst": 150,
        "active_start_hour_utc": 8,
        "active_end_hour_utc": 20,
    },
]

ACCOUNT_IDS = [a["id"] for a in ACCOUNTS]
ACCOUNT_MAP = {a["id"]: a for a in ACCOUNTS}

SCHEDULER_INTERVAL_MINUTES = 15
DATABASE_PATH = os.environ.get("DATABASE_PATH", "threads_killer.db")
