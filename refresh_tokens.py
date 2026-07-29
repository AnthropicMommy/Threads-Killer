"""
Refreshes each account's long-lived token weekly. Prints results as
ACC_ID=NEW_TOKEN lines; the workflow parses these and updates the
corresponding repo secrets via `gh secret set`.
"""

import json
import os
import requests

accounts = json.load(open("accounts.json"))

for account in accounts:
    token = os.environ.get(account["token_secret"])
    if not token:
        continue
    resp = requests.get(
        "https://graph.threads.net/refresh_access_token",
        params={"grant_type": "th_refresh_token", "access_token": token},
    )
    resp.raise_for_status()
    new_token = resp.json()["access_token"]
    print(f"{account['token_secret']}={new_token}")
