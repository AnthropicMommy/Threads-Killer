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

WEBHOOK_SECRET = os.environ.get("WEBHOOK_SECRET", "threads-killer-webhook")


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

    responses = {
        "/start": (
            "Threads Killer Bot\n\n"
            "Commands:\n"
            "/add <acc> <text> - Add post\n"
            "/edit <acc> <id> <text> - Edit post\n"
            "/remove <acc> <id> - Remove post\n"
            "/list <acc> - List queue\n"
            "/status [acc] - Show status\n"
            "/cooldown <acc|all> - Pause\n"
            "/resume <acc|all> - Resume"
        ),
        "/help": None,
    }

    if cmd in ("/start", "/help"):
        send_message(chat_id, responses.get("/start") or responses["/start"])
        return

    if cmd == "/add":
        if len(args) < 2:
            send_message(chat_id, "Usage: /add <acc> <text>")
            return
        acc_id = args[0].lower()
        if acc_id not in ACCOUNT_IDS:
            send_message(chat_id, f"Unknown: {acc_id}. Valid: {', '.join(ACCOUNT_IDS)}")
            return
        text = " ".join(args[1:])
        post_id = storage.add_post(acc_id, text)
        send_message(chat_id, f"Added to {acc_id}.\nID: {post_id}")
        return

    if cmd == "/edit":
        if len(args) < 3:
            send_message(chat_id, "Usage: /edit <acc> <id> <text>")
            return
        acc_id = args[0].lower()
        post_id = args[1]
        new_text = " ".join(args[2:])
        if storage.edit_post(acc_id, post_id, new_text):
            send_message(chat_id, f"Updated {post_id} in {acc_id}.")
        else:
            send_message(chat_id, f"Post {post_id} not found.")
        return

    if cmd == "/remove":
        if len(args) < 2:
            send_message(chat_id, "Usage: /remove <acc> <id>")
            return
        acc_id = args[0].lower()
        post_id = args[1]
        storage.remove_post(acc_id, post_id)
        send_message(chat_id, f"Removed {post_id} from {acc_id}.")
        return

    if cmd == "/list":
        if not args:
            send_message(chat_id, "Usage: /list <acc>")
            return
        acc_id = args[0].lower()
        if acc_id not in ACCOUNT_IDS:
            send_message(chat_id, f"Unknown: {acc_id}")
            return
        posts = storage.get_queue(acc_id)
        if not posts:
            send_message(chat_id, f"{acc_id} queue empty.")
            return
        lines = [f"{acc_id} ({len(posts)} posts):\n"]
        for p in posts:
            preview = p["text"][:60].replace("\n", " ")
            lines.append(f"[{p['id']}] ({p.get('times_posted', 0)}x) {preview}")
        send_message(chat_id, "\n".join(lines))
        return

    if cmd == "/status":
        acc_ids = ACCOUNT_IDS
        if args and args[0].lower() in ACCOUNT_IDS:
            acc_ids = [args[0].lower()]
        elif args and args[0].lower() == "all":
            acc_ids = ACCOUNT_IDS
        lines = []
        for acc_id in acc_ids:
            account = ACCOUNT_MAP[acc_id]
            posts = storage.get_queue(acc_id)
            paused = storage.is_paused(acc_id)
            state = "PAUSED" if paused else "ACTIVE"
            hours = f"{account['active_start_hour_utc']}-{account['active_end_hour_utc']} UTC"
            lines.append(
                f"{acc_id} [{state}]\n"
                f"  Queue: {len(posts)} posts\n"
                f"  Active: {hours}\n"
                f"  Burst: {account['posts_per_burst']} per 15min"
            )
        send_message(chat_id, "\n\n".join(lines))
        return

    if cmd == "/cooldown":
        if not args:
            send_message(chat_id, "Usage: /cooldown <acc|all>")
            return
        target = args[0].lower()
        if target == "all":
            storage.set_cooldown_all(True)
            send_message(chat_id, "All accounts paused.")
        elif target in ACCOUNT_IDS:
            storage.set_cooldown(target, True)
            send_message(chat_id, f"{target} paused.")
        else:
            send_message(chat_id, f"Unknown: {target}")
        return

    if cmd == "/resume":
        if not args:
            send_message(chat_id, "Usage: /resume <acc|all>")
            return
        target = args[0].lower()
        if target == "all":
            storage.set_cooldown_all(False)
            send_message(chat_id, "All accounts resumed.")
        elif target in ACCOUNT_IDS:
            storage.set_cooldown(target, False)
            send_message(chat_id, f"{target} resumed.")
        else:
            send_message(chat_id, f"Unknown: {target}")
        return

    send_message(chat_id, "Unknown command. Send /help for commands.")


def send_message(chat_id, text):
    import requests
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        requests.post(url, json={"chat_id": chat_id, "text": text})
    except Exception as e:
        logger.error(f"Failed to send message: {e}")


def run_trigger():
    from datetime import datetime, timezone

    results = []
    for account in ACCOUNTS:
        acc_id = account["id"]

        if storage.is_paused(acc_id):
            results.append(f"[{acc_id}] paused, skip")
            continue

        now = datetime.now(timezone.utc)
        start = account.get("active_start_hour_utc", 0)
        end = account.get("active_end_hour_utc", 24)
        if not (start <= now.hour < end):
            results.append(f"[{acc_id}] outside window, skip")
            continue

        post = storage.get_next_post(acc_id)
        if not post:
            results.append(f"[{acc_id}] queue empty, skip")
            continue

        result = publish_one(acc_id, post)
        if isinstance(result, tuple) and result[0] is None:
            storage.update_post_stats(acc_id, post["id"], error=result[1])
            results.append(f"[{acc_id}] FAILED: {result[1]}")
        else:
            storage.update_post_stats(acc_id, post["id"], media_id=result)
            results.append(f"[{acc_id}] posted: {post['text'][:40]}...")

    return "\n".join(results) if results else "Nothing to post"


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


class Handler(BaseHTTPRequestHandler):
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
                self.wfile.write(b'{"ok": true}')
            except Exception as e:
                logger.error(f"Webhook error: {e}")
                self.send_response(500)
                self.end_headers()
        elif self.path == "/api/trigger":
            result = run_trigger()
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(result.encode())
        else:
            self.send_response(404)
            self.end_headers()

    def do_GET(self):
        if self.path == "/api/health":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain")
            self.end_headers()
            self.wfile.write(b"ok")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        logger.info(format % args)
