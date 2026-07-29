import os
import time
import sys

import requests

from config import ACCOUNT_MAP

GRAPH_BASE = "https://graph.threads.net/v1.0"


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


def publish_one(account_id, post):
    account = ACCOUNT_MAP[account_id]
    token = os.environ.get(account["token_env"])
    user_id = os.environ.get(account["user_id_env"])
    if not token or not user_id:
        print(f"[{account_id}] missing secrets, skipping", file=sys.stderr)
        return

    text = post["text"]
    print(f"[{account_id}] publishing: {text[:50]}...")
    try:
        creation_id = create_container(user_id, token, text)
        media_id = publish_container(user_id, token, creation_id)
        print(f"[{account_id}] -> published, media id {media_id}")
        return media_id
    except requests.HTTPError as e:
        error_text = e.response.text
        print(f"[{account_id}] -> FAILED: {error_text}", file=sys.stderr)
        return None, error_text
