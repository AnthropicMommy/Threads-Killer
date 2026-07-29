import logging
import threading

from flask import Flask
from telegram import Update
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
)

from config import TELEGRAM_BOT_TOKEN
import db
import telegram_bot as handlers
from scheduler import run_scheduled_posting

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

app = Flask(__name__)


@app.route("/health")
def health():
    return "ok", 200


def run_flask():
    port = int(__import__("os").environ.get("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)


def main():
    db.init_db()
    logger.info("Database initialized")

    flask_thread = threading.Thread(target=run_flask, daemon=True)
    flask_thread.start()
    logger.info("Health endpoint started")

    logger.info("Starting Telegram bot...")
    application = ApplicationBuilder().token(TELEGRAM_BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", handlers.cmd_start))
    application.add_handler(CommandHandler("help", handlers.cmd_help))
    application.add_handler(CommandHandler("add", handlers.cmd_add))
    application.add_handler(CommandHandler("edit", handlers.cmd_edit))
    application.add_handler(CommandHandler("remove", handlers.cmd_remove))
    application.add_handler(CommandHandler("list", handlers.cmd_list))
    application.add_handler(CommandHandler("status", handlers.cmd_status))
    application.add_handler(CommandHandler("cooldown", handlers.cmd_cooldown))
    application.add_handler(CommandHandler("resume", handlers.cmd_resume))

    application.job_queue.run_repeating(
        lambda ctx: run_scheduled_posting(),
        interval=900,
        first=10,
    )

    application.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
