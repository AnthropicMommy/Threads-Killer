"""
ONE-TIME SETUP SCRIPT
Run this locally to get your long-lived Threads access token.

Steps:
1. Fill in APP_ID, APP_SECRET, REDIRECT_URI below (from developers.facebook.com app settings)
2. Run this script: python get_long_lived_token.py
3. It prints an authorize URL -> open it in your browser, log in as the TESTER account,
   approve, and you'll be redirected to your REDIRECT_URI with ?code=... in the URL
4. Paste that code back into this script when prompted
5. It prints your long-lived token + your Threads user ID -> save both as GitHub secrets
   (THREADS_ACCESS_TOKEN and THREADS_USER_ID)
"""

import requests
import urllib.parse

APP_ID = "YOUR_APP_ID"
APP_SECRET = "YOUR_APP_SECRET"
# Must exactly match a redirect URI registered in your Meta app's Threads settings.
# For local testing you can use https://localhost/ (Meta allows this for dev/testers)
REDIRECT_URI = "https://localhost/"

SCOPES = "threads_basic,threads_content_publish"

def step1_get_auth_url():
    params = {
        "client_id": APP_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
        "response_type": "code",
    }
    url = "https://threads.net/oauth/authorize?" + urllib.parse.urlencode(params)
    print("\n1) Open this URL, log in as the tester, and approve:\n")
    print(url)
    print()

def step2_exchange_code(code):
    resp = requests.post(
        "https://graph.threads.net/oauth/access_token",
        data={
            "client_id": APP_ID,
            "client_secret": APP_SECRET,
            "grant_type": "authorization_code",
            "redirect_uri": REDIRECT_URI,
            "code": code,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    short_lived_token = data["access_token"]
    user_id = data["user_id"]
    print(f"\nShort-lived token obtained. User ID: {user_id}")
    return short_lived_token, user_id

def step3_exchange_for_long_lived(short_lived_token):
    resp = requests.get(
        "https://graph.threads.net/access_token",
        params={
            "grant_type": "th_exchange_token",
            "client_secret": APP_SECRET,
            "access_token": short_lived_token,
        },
    )
    resp.raise_for_status()
    data = resp.json()
    return data["access_token"], data.get("expires_in")

if __name__ == "__main__":
    step1_get_auth_url()
    redirected_url = input("2) Paste the FULL redirect URL you landed on: ").strip()
    parsed = urllib.parse.urlparse(redirected_url)
    code = urllib.parse.parse_qs(parsed.query).get("code", [None])[0]
    if not code:
        raise SystemExit("Couldn't find ?code= in that URL. Copy the full address bar contents.")
    # Meta sometimes appends #_ to the code — strip it
    code = code.split("#")[0]

    short_lived_token, user_id = step2_exchange_code(code)
    long_lived_token, expires_in = step3_exchange_for_long_lived(short_lived_token)

    days = round(expires_in / 86400, 1) if expires_in else "~60"
    print("\n" + "=" * 60)
    print("SUCCESS — save these as GitHub repo secrets:")
    print("=" * 60)
    print(f"THREADS_ACCESS_TOKEN = {long_lived_token}")
    print(f"THREADS_USER_ID      = {user_id}")
    print(f"\n(Token valid for ~{days} days. The refresh workflow will keep it alive.)")
