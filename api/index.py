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

Quick commands:
/a <text> - Add post
/al - List posts
/as - Status
/ac - Clear queue
/ar <id> - Remove post
/ae <id> <new text> - Edit post
/go - Post now
/p - Pause
/r - Resume
/h - Help"""


def handle_telegram_update(update):
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

    if cmd in ("/start", "/h", "/help"):
        send_message(chat_id, HELP_TEXT)
        return

    if cmd in ("/a", "/add"):
        if len(args) < 1:
            send_message(chat_id, "Usage: /a <text>")
            return
        post_text = text.split(maxsplit=1)[1] if len(text.split(maxsplit=1)) > 1 else ""
        if not post_text:
            send_message(chat_id, "Usage: /a <text>")
            return
        post_id = storage.add_post("acc1", post_text)
        send_message(chat_id, f"Added!\nID: {post_id}")
        return

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

    if cmd in ("/as", "/status"):
        posts = storage.get_queue("acc1")
        paused = storage.is_paused("acc1")
        state = "PAUSED" if paused else "ACTIVE"
        lines = [
            f"acc1 [{state}]",
            f"  Queue: {len(posts)} posts",
            f"  Posts loop every 15 min",
        ]
        send_message(chat_id, "\n".join(lines))
        return

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

    if cmd in ("/ac", "/clear"):
        storage.clear_queue("acc1")
        send_message(chat_id, "Queue cleared.")
        return

    if cmd in ("/p", "/pause"):
        storage.set_cooldown("acc1", True)
        send_message(chat_id, "Posting paused.")
        return

    if cmd in ("/r", "/resume"):
        storage.set_cooldown("acc1", False)
        send_message(chat_id, "Posting resumed.")
        return

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
    results = []
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
    return "\n".join(results) if results else "Nothing to post"


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
