"""
Refreshes each account's long-lived token.
Run manually: python refresh_tokens.py
Or add a /refresh command to the Telegram bot.
"""

import os
import requests

from config import ACCOUNTS

for account in ACCOUNTS:
    token = os.environ.get(account["token_env"])
    if not token:
        print(f"[{account['id']}] no token found, skipping")
        continue
    try:
        resp = requests.get(
            "https://graph.threads.net/refresh_access_token",
            params={"grant_type": "th_refresh_token", "access_token": token},
        )
        resp.raise_for_status()
        new_token = resp.json()["access_token"]
        print(f"[{account['id']}] NEW_TOKEN={new_token}")
    except requests.HTTPError as e:
        print(f"[{account['id']}] FAILED: {e.response.text}")
