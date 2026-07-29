import json
import os
import sys
import logging
from http.server import BaseHTTPRequestHandler

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import TELEGRAM_BOT_TOKEN, ACCOUNT_IDS, ACCOUNT_MAP
import storage
from threads_api import publish_one

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

storage.init_db()

ACCOUNTS = [
    {
        "id": "acc1",
        "token_env": "THREADS_ACCESS_TOKEN_ACC1",
        "user_id_env": "THREADS_USER_ID_ACC1",
        "posts_per_burst": 10,
        "active_start_hour_utc": 5,
        "active_end_hour_utc": 17,
    },
]

HELP_TEXT = """Threads Killer Bot

Queue:
/a <text> - Add post
/al - List posts
/as - Status
/ac - Clear queue
/ar <id> - Remove
/ae <id> <text> - Edit
/go - Post now
/p - Pause
/r - Resume

X Cross-poster:
/src add <username> - Monitor X profile
/src list - List sources
/src rm <username> - Remove source
/src scan - Scan now

/h - Help"""


def handle_telegram_update(update):
    try:
        _handle_update(update)
    except Exception as e:
        logger.error(f"Handler error: {e}", exc_info=True)


def _handle_update(update):
    if "message" not in update:
        return
    message = update["message"]
    text = message.get("text", "")
    chat_id = message["chat"]["id"]

    if not text.startswith("/"):
        return

    parts = text.split(maxsplit=2)
    cmd = parts[0].lower()
    args = parts[1:]

    # --- Help ---
    if cmd in ("/start", "/h", "/help"):
        send_message(chat_id, HELP_TEXT)
        return

    # --- Add post ---
    if cmd in ("/a", "/add"):
        if len(args) < 1:
            send_message(chat_id, "Usage: /a <text>")
            return
        post_text = " ".join(parts[1:])
        if not post_text:
            send_message(chat_id, "Usage: /a <text>")
            return
        post_id = storage.add_post("acc1", post_text)
        send_message(chat_id, f"Added!\nID: {post_id}")
        return

    # --- List posts ---
    if cmd in ("/al", "/list"):
        posts = storage.get_queue("acc1")
        if not posts:
            send_message(chat_id, "Queue empty.")
            return
        lines = [f"Queue ({len(posts)} posts):\n"]
        for p in posts:
            preview = p["text"][:80].replace("\n", " ")
            lines.append(f"[{p['id']}] {preview}")
        send_message(chat_id, "\n".join(lines))
        return

    # --- Status ---
    if cmd in ("/as", "/status"):
        posts = storage.get_queue("acc1")
        paused = storage.is_paused("acc1")
        state = "PAUSED" if paused else "ACTIVE"
        sources = storage.get_sources()
        lines = [
            f"acc1 [{state}]",
            f"  Queue: {len(posts)} posts",
            f"  X sources: {len(sources)}",
        ]
        send_message(chat_id, "\n".join(lines))
        return

    # --- Remove post ---
    if cmd in ("/ar", "/rm", "/remove"):
        if not args:
            send_message(chat_id, "Usage: /ar <id>")
            return
        post_id = args[0]
        if storage.remove_post("acc1", post_id):
            send_message(chat_id, f"Removed {post_id}.")
        else:
            send_message(chat_id, f"Post {post_id} not found.")
        return

    # --- Edit post ---
    if cmd in ("/ae", "/ed", "/edit"):
        if len(args) < 2:
            send_message(chat_id, "Usage: /ae <id> <new text>")
            return
        post_id = args[0]
        new_text = " ".join(args[1:])
        if storage.edit_post("acc1", post_id, new_text):
            send_message(chat_id, f"Updated {post_id}.")
        else:
            send_message(chat_id, f"Post {post_id} not found.")
        return

    # --- Clear queue ---
    if cmd in ("/ac", "/clear"):
        storage.clear_queue("acc1")
        send_message(chat_id, "Queue cleared.")
        return

    # --- Pause ---
    if cmd in ("/p", "/pause"):
        storage.set_cooldown("acc1", True)
        send_message(chat_id, "Posting paused.")
        return

    # --- Resume ---
    if cmd in ("/r", "/resume"):
        storage.set_cooldown("acc1", False)
        send_message(chat_id, "Posting resumed.")
        return

    # --- Post now ---
    if cmd in ("/go", "/post", "/now"):
        posts = storage.get_queue("acc1")
        if not posts:
            send_message(chat_id, "Queue empty.")
            return
        post = storage.get_next_post("acc1")
        if not post:
            send_message(chat_id, "Nothing to post.")
            return
        send_message(chat_id, f"Posting: {post['text'][:50]}...")
        result = publish_one("acc1", post)
        if isinstance(result, tuple) and result[0] is None:
            storage.update_post_stats("acc1", post["id"], error=result[1])
            send_message(chat_id, f"FAILED: {result[1][:200]}")
        else:
            storage.update_post_stats("acc1", post["id"], media_id=result)
            send_message(chat_id, f"Posted! ID: {post['id']}")
        return

    # --- X Sources ---
    if cmd == "/src":
        if not args:
            send_message(chat_id, "Usage: /src add|list|rm|scan <username>")
            return
        sub = args[0].lower()

        if sub == "add":
            if len(args) < 2:
                send_message(chat_id, "Usage: /src add <x_username>")
                return
            username = args[1].lstrip("@")
            storage.add_source(username)
            send_message(chat_id, f"Monitoring @{username}")
            return

        if sub == "list":
            sources = storage.get_sources()
            if not sources:
                send_message(chat_id, "No X sources.")
                return
            lines = [f"X Sources ({len(sources)}):\n"]
            for s in sources:
                lines.append(f"@{s}")
            send_message(chat_id, "\n".join(lines))
            return

        if sub in ("rm", "remove"):
            if len(args) < 2:
                send_message(chat_id, "Usage: /src rm <username>")
                return
            username = args[1].lstrip("@")
            if storage.remove_source(username):
                send_message(chat_id, f"Removed @{username}")
            else:
                send_message(chat_id, f"@{username} not found.")
            return

        if sub == "scan":
            send_message(chat_id, "Scanning X profiles...")
            result = storage.scan_and_queue("acc1")
            send_message(chat_id, result)
            return

        if sub == "preview":
            if len(args) < 2:
                send_message(chat_id, "Usage: /src preview <username>")
                return
            username = args[1].lstrip("@")
            send_message(chat_id, f"Fetching latest from @{username}...")
            tweets = storage.fetch_tweets_from_x(username)
            if not tweets:
                send_message(chat_id, f"Couldn't fetch tweets for @{username}. Nitter might be down.")
                return
            latest = tweets[0]
            send_message(chat_id, f"@{username} latest:\n\n{latest['text'][:500]}")
            return

        send_message(chat_id, "Unknown subcommand. Use: /src add|list|rm|scan|preview")
        return

    send_message(chat_id, "Unknown command. Send /h for help.")


def send_message(chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(url, json={"chat_id": chat_id, "text": text}, timeout=10)
        logger.info(f"Send message to {chat_id}: status={resp.status_code}")
    except Exception as e:
        logger.error(f"Failed to send message: {e}")


def run_trigger():
    from datetime import datetime, timezone

    scan_result = storage.scan_and_queue("acc1")
    logger.info(f"Scan result: {scan_result}")

    results = [f"Scan: {scan_result}"]

    for account in ACCOUNTS:
        acc_id = account["id"]
        if storage.is_paused(acc_id):
            results.append(f"[{acc_id}] paused")
            continue
        now = datetime.now(timezone.utc)
        start = account.get("active_start_hour_utc", 0)
        end = account.get("active_end_hour_utc", 24)
        if not (start <= now.hour < end):
            results.append(f"[{acc_id}] outside window ({start}-{end} UTC)")
            continue
        post = storage.get_next_post(acc_id)
        if not post:
            results.append(f"[{acc_id}] queue empty")
            continue
        result = publish_one(acc_id, post)
        if isinstance(result, tuple) and result[0] is None:
            storage.update_post_stats(acc_id, post["id"], error=result[1])
            results.append(f"[{acc_id}] FAILED: {result[1][:100]}")
        else:
            storage.update_post_stats(acc_id, post["id"], media_id=result)
            results.append(f"[{acc_id}] posted: {post['text'][:40]}...")
    return "\n".join(results) if results else "Nothing to do"


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(content_length) if content_length else b""

        if self.path == "/api/webhook":
            try:
                update = json.loads(body)
                handle_telegram_update(update)
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(b'{"ok":true}')
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                self.send_response(500)
                self.end_headers()
        elif self.path == "/api/trigger":
            try:
                result = run_trigger()
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(result.encode())
            except Exception as e:
                logger.error(f"Trigger error: {e}")
                self.send_response(500)
                self.end_headers()
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path in ("/api/health", "/health"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"Threads Killer Bot - running")

    def log_message(self, format, *args):
        logger.info(format % args)
