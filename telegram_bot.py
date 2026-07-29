from telegram import Update
from telegram.ext import ContextTypes

from config import ACCOUNT_IDS, ACCOUNT_MAP
import db


def parse_account_arg(args, require_text=False):
    if not args:
        return None, None, "Missing account ID. Usage: /command <account> [text]"
    acc_id = args[0].lower()
    if acc_id not in ACCOUNT_IDS:
        return None, None, f"Unknown account: {acc_id}. Valid: {', '.join(ACCOUNT_IDS)}"
    text = " ".join(args[1:]) if len(args) > 1 else None
    if require_text and not text:
        return None, None, f"Missing text. Usage: /{args[0]} {acc_id} <text>"
    return acc_id, text, None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Threads Killer Bot\n\n"
        "Commands:\n"
        "/add <acc> <text> - Add post to queue\n"
        "/edit <acc> <id> <text> - Edit post\n"
        "/remove <acc> <id> - Remove post\n"
        "/list <acc> - List queue\n"
        "/status [acc] - Show status\n"
        "/cooldown <acc|all> - Pause posting\n"
        "/resume <acc|all> - Resume posting\n"
        "/help - Show this message"
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_start(update, context)


async def cmd_add(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc_id, text, err = parse_account_arg(context.args, require_text=True)
    if err:
        await update.message.reply_text(err)
        return
    post_id = db.add_post(acc_id, text)
    await update.message.reply_text(f"Added to {acc_id} queue.\nID: {post_id}")


async def cmd_edit(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 3:
        await update.message.reply_text("Usage: /edit <acc> <id> <new text>")
        return
    acc_id = context.args[0].lower()
    if acc_id not in ACCOUNT_IDS:
        await update.message.reply_text(f"Unknown account: {acc_id}")
        return
    post_id = context.args[1]
    new_text = " ".join(context.args[2:])
    if db.edit_post(acc_id, post_id, new_text):
        await update.message.reply_text(f"Updated post {post_id} in {acc_id}.")
    else:
        await update.message.reply_text(f"Post {post_id} not found in {acc_id}.")


async def cmd_remove(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args or len(context.args) < 2:
        await update.message.reply_text("Usage: /remove <acc> <id>")
        return
    acc_id = context.args[0].lower()
    if acc_id not in ACCOUNT_IDS:
        await update.message.reply_text(f"Unknown account: {acc_id}")
        return
    post_id = context.args[1]
    if db.remove_post(acc_id, post_id):
        await update.message.reply_text(f"Removed post {post_id} from {acc_id}.")
    else:
        await update.message.reply_text(f"Post {post_id} not found in {acc_id}.")


async def cmd_list(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /list <acc>")
        return
    acc_id = context.args[0].lower()
    if acc_id not in ACCOUNT_IDS:
        await update.message.reply_text(f"Unknown account: {acc_id}")
        return
    queue = db.get_queue(acc_id)
    if not queue:
        await update.message.reply_text(f"{acc_id} queue is empty.")
        return
    lines = [f"{acc_id} Queue ({len(queue)} posts):\n"]
    for p in queue:
        preview = p["text"][:60].replace("\n", " ")
        lines.append(f"[{p['id']}] ({p['times_posted']}x) {preview}")
    await update.message.reply_text("\n".join(lines))


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    acc_ids = ACCOUNT_IDS
    if context.args:
        acc_id = context.args[0].lower()
        if acc_id == "all":
            acc_ids = ACCOUNT_IDS
        elif acc_id in ACCOUNT_IDS:
            acc_ids = [acc_id]
        else:
            await update.message.reply_text(f"Unknown account: {acc_id}")
            return

    lines = []
    for acc_id in acc_ids:
        account = ACCOUNT_MAP[acc_id]
        queue_size = db.get_queue_size(acc_id)
        paused = db.is_paused(acc_id)
        state = "PAUSED" if paused else "ACTIVE"
        hours = f"{account['active_start_hour_utc']}-{account['active_end_hour_utc']} UTC"
        lines.append(
            f"{acc_id} [{state}]\n"
            f"  Queue: {queue_size} posts\n"
            f"  Active hours: {hours}\n"
            f"  Burst: {account['posts_per_burst']} posts every 15 min"
        )
    await update.message.reply_text("\n\n".join(lines))


async def cmd_cooldown(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /cooldown <acc|all>")
        return
    target = context.args[0].lower()
    if target == "all":
        db.set_cooldown_all(True)
        await update.message.reply_text("All accounts paused.")
    elif target in ACCOUNT_IDS:
        db.set_cooldown(target, True)
        await update.message.reply_text(f"{target} paused.")
    else:
        await update.message.reply_text(f"Unknown: {target}. Use account ID or 'all'.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /resume <acc|all>")
        return
    target = context.args[0].lower()
    if target == "all":
        db.set_cooldown_all(False)
        await update.message.reply_text("All accounts resumed.")
    elif target in ACCOUNT_IDS:
        db.set_cooldown(target, False)
        await update.message.reply_text(f"{target} resumed.")
    else:
        await update.message.reply_text(f"Unknown: {target}. Use account ID or 'all'.")
