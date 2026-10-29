import os
import logging
import asyncio
import random
import sqlite3
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, TelegramError, Conflict
from telegram.ext import (
    Application, ApplicationBuilder, CommandHandler,
    ContextTypes, MessageHandler, filters,
)

BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# First reminder 3 hours after /start, then every 3 hours.
REMINDER_INTERVAL_SECONDS = 3 * 60 * 60
# The bot checks due times once a minute; it does NOT message every minute.
CHECK_INTERVAL_SECONDS = 60

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "855goal_users.sqlite3"

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("G168-SPORT")

WELCOME_TEXT = """Welcome To G168-SPORT

សូមស្វាគមន៍មកកាន់ G168-SPORT!

ទទួលបានព័ត៌មានកីឡា ព័ត៌មានបាល់ទាត់ លទ្ធផល និងព័ត៌មានថ្មីៗនៅទីយើង។

សូមជ្រើសរើសជម្រើសខាងក្រោម 👇"""

KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton("💬 DM NOW", url="https://t.me/GOALWIN855")],
    [InlineKeyboardButton("🌐 WEBSITE", url="https://heylink.me/855goal/")],
    [InlineKeyboardButton("📢 CHANNEL UPDATE", url="https://t.me/Game855GOAL")],
])

# Keep all six original JPG files in the same GitHub folder as bot.py.
WELCOME_IMAGE = BASE_DIR / "5985379721660800813.jpg"
ROTATION_IMAGES = [
    BASE_DIR / "5985379721660800808.jpg",
    BASE_DIR / "5985379721660800809.jpg",
    BASE_DIR / "5985379721660800810.jpg",
    BASE_DIR / "5985379721660800811.jpg",
    BASE_DIR / "5985379721660800812.jpg",
]

PROMO_MESSAGES_KH = [
    "⚽ សូមតាមដានព័ត៌មានកីឡា និងព័ត៌មានបាល់ទាត់ថ្មីៗរបស់យើង!",
    "🏆 ស្វែងយល់ពីព័ត៌មានក្រុមបាល់ទាត់ និងលទ្ធផលប្រកួតថ្មីៗ។",
    "📢 ចូលរួមជាមួយសហគមន៍របស់យើង ដើម្បីទទួលបានព័ត៌មានថ្មីៗ។",
    "🌐 សូមចូលមើលគេហទំព័ររបស់យើងសម្រាប់ព័ត៌មានបន្ថែម។",
    "⚽ តាមដានបច្ចុប្បន្នភាពកីឡាជាមួយ G168-SPORT!",
]


def db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            active INTEGER NOT NULL DEFAULT 1
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            name TEXT PRIMARY KEY,
            value INTEGER NOT NULL
        )
    """)
    conn.execute("""
        INSERT OR IGNORE INTO settings (name, value)
        VALUES ('image_index', 0)
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS start_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_start REAL NOT NULL
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_schedules (
            user_id INTEGER PRIMARY KEY,
            next_send REAL NOT NULL
        )
    """)
    conn.commit()
    return conn


def register_user(user_id):
    conn = db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO users (user_id, active) VALUES (?, 1)
                ON CONFLICT(user_id) DO UPDATE SET active = 1
            """, (user_id,))
    finally:
        conn.close()


def deactivate_user(user_id):
    conn = db_connection()
    try:
        with conn:
            conn.execute("UPDATE users SET active = 0 WHERE user_id = ?", (user_id,))
            conn.execute("DELETE FROM user_schedules WHERE user_id = ?", (user_id,))
    finally:
        conn.close()


def clear_cooldown(user_id):
    conn = db_connection()
    try:
        with conn:
            conn.execute("DELETE FROM start_cooldowns WHERE user_id = ?", (user_id,))
    finally:
        conn.close()


def count_active_users():
    conn = db_connection()
    try:
        row = conn.execute("SELECT COUNT(*) FROM users WHERE active = 1").fetchone()
        return row[0] if row else 0
    finally:
        conn.close()


def get_next_image():
    conn = db_connection()
    try:
        with conn:
            row = conn.execute(
                "SELECT value FROM settings WHERE name = 'image_index'"
            ).fetchone()
            index = (row[0] if row else 0) % len(ROTATION_IMAGES)
            following = (index + 1) % len(ROTATION_IMAGES)
            conn.execute("""
                INSERT INTO settings (name, value) VALUES ('image_index', ?)
                ON CONFLICT(name) DO UPDATE SET value = excluded.value
            """, (following,))
    finally:
        conn.close()
    return ROTATION_IMAGES[index]


def welcome_cooldown_remaining(user_id, now):
    conn = db_connection()
    try:
        row = conn.execute(
            "SELECT last_start FROM start_cooldowns WHERE user_id = ?",
            (user_id,),
        ).fetchone()
    finally:
        conn.close()
    if row is None:
        return 0
    return max(0, int(REMINDER_INTERVAL_SECONDS - (now - row[0])))


def record_start_and_schedule(user_id, now):
    conn = db_connection()
    try:
        with conn:
            conn.execute("""
                INSERT INTO start_cooldowns (user_id, last_start) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET last_start = excluded.last_start
            """, (user_id, now))
            conn.execute("""
                INSERT INTO user_schedules (user_id, next_send) VALUES (?, ?)
                ON CONFLICT(user_id) DO UPDATE SET next_send = excluded.next_send
            """, (user_id, now + REMINDER_INTERVAL_SECONDS))
    finally:
        conn.close()


def get_due_users(now):
    conn = db_connection()
    try:
        rows = conn.execute("""
            SELECT s.user_id
            FROM user_schedules s
            JOIN users u ON u.user_id = s.user_id
            WHERE u.active = 1 AND s.next_send <= ?
        """, (now,)).fetchall()
        return [row[0] for row in rows]
    finally:
        conn.close()


def push_next_send(user_id):
    conn = db_connection()
    try:
        with conn:
            conn.execute("""
                UPDATE user_schedules SET next_send = ? WHERE user_id = ?
            """, (time.time() + REMINDER_INTERVAL_SECONDS, user_id))
    finally:
        conn.close()


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    user = update.effective_user
    if message is None or user is None:
        return

    now = time.time()
    remaining = welcome_cooldown_remaining(user.id, now)
    if remaining > 0:
        hours, remainder = divmod(remaining, 3600)
        minutes = (remainder + 59) // 60
        await message.reply_text(
            "⏳ You have already started G168-SPORT.\n\n"
            f"Please try again in about {hours}h {minutes}m."
        )
        return

    record_start_and_schedule(user.id, now)
    register_user(user.id)
    logger.info("Welcome sent to %s; first reminder in 3 hours.", user.id)

    if not WELCOME_IMAGE.is_file():
        logger.error("Welcome image missing: %s", WELCOME_IMAGE)
        await message.reply_text(WELCOME_TEXT, reply_markup=KEYBOARD)
        return

    try:
        with WELCOME_IMAGE.open("rb") as photo:
            await message.reply_photo(
                photo=photo, caption=WELCOME_TEXT, reply_markup=KEYBOARD
            )
    except TelegramError:
        logger.exception("Failed to send welcome image")
        await message.reply_text(WELCOME_TEXT, reply_markup=KEYBOARD)


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message
    if user:
        deactivate_user(user.id)
        clear_cooldown(user.id)
    if message:
        await message.reply_text(
            "Automatic updates stopped. Send /start to subscribe again."
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message:
        await message.reply_text(
            "✅ G168-SPORT bot is running.\n"
            "First automatic reminder: 3 hours after /start.\n"
            "Repeat interval: every 3 hours.\n"
            f"Active subscribers: {count_active_users()}."
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message:
        await message.reply_text(
            "G168-SPORT Bot Help ⚽\n\n"
            "/start - Welcome image and subscribe\n"
            "/status - Check bot status\n"
            "/stop - Stop automatic reminders\n"
            "Send a message to receive a basic bot response.",
            reply_markup=KEYBOARD,
        )


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.effective_message
    if message is None or not message.text:
        return
    text = message.text.strip().lower()

    if any(word in text for word in ("hello", "hi", "hey", "សួស្តី")):
        reply = (
            "សួស្តី! សូមស្វាគមន៍មកកាន់ G168-SPORT ⚽\n"
            "វាយ /help សម្រាប់ជំនួយ ឬប្រើប៊ូតុងខាងក្រោម។"
        )
    elif any(word in text for word in ("football", "soccer", "sport", "បាល់ទាត់", "កីឡា")):
        reply = (
            "⚽ សូមតាមដានព័ត៌មានកីឡា និងព័ត៌មានបាល់ទាត់ថ្មីៗ "
            "តាមរយៈ Channel Update របស់យើង។"
        )
    else:
        reply = (
            "សូមអរគុណសម្រាប់សាររបស់អ្នក! ⚽\n"
            "សម្រាប់ព័ត៌មានបន្ថែម សូមប្រើប៊ូតុង WEBSITE ឬ CHANNEL UPDATE។"
        )
    await message.reply_text(reply, reply_markup=KEYBOARD)


async def broadcast(context: ContextTypes.DEFAULT_TYPE):
    due_users = get_due_users(time.time())
    if not due_users:
        return

    image_path = get_next_image()
    if not image_path.is_file():
        logger.error("Scheduled image missing: %s", image_path)
        return

    caption = (
        "⚽ G168-SPORT Update\n\n"
        + random.choice(PROMO_MESSAGES_KH)
        + "\n\n🌐 Website: https://heylink.me/855goal/"
        + "\n📢 Channel: https://t.me/Game855GOAL"
    )
    image_bytes = image_path.read_bytes()

    for user_id in due_users:
        # Advance the timer before sending to prevent rapid retries on errors.
        push_next_send(user_id)
        try:
            await context.bot.send_photo(
                chat_id=user_id,
                photo=image_bytes,
                caption=caption,
                reply_markup=KEYBOARD,
            )
            await asyncio.sleep(0.05)
        except Forbidden:
            deactivate_user(user_id)
            logger.info("User blocked bot: %s", user_id)
        except TelegramError:
            logger.exception("Failed sending reminder to user %s", user_id)


async def on_error(update, context: ContextTypes.DEFAULT_TYPE):
    if isinstance(context.error, Conflict):
        logger.error(
            "Another bot process is using this token. Stop the other "
            "Render service or local copy so only one polling process runs."
        )
        return
    logger.error("Unhandled error", exc_info=context.error)


def start_health_server():
    # Optional for Render Web Services. Not needed for Background Workers.
    port = os.getenv("PORT")
    if not port:
        return

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"G168-SPORT bot is running")

        def do_HEAD(self):
            self.send_response(200)
            self.end_headers()

        def log_message(self, *args):
            pass

    server = HTTPServer(("0.0.0.0", int(port)), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    logger.info("Health server listening on port %s", port)


async def post_init(application: Application):
    conn = db_connection()
    conn.close()

    me = await application.bot.get_me()
    logger.info("Connected to Telegram as @%s", me.username)

    all_images = [WELCOME_IMAGE, *ROTATION_IMAGES]
    missing = [path.name for path in all_images if not path.is_file()]
    if missing:
        logger.warning("Missing image files: %s", ", ".join(missing))

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue unavailable. Install "
            "python-telegram-bot[job-queue]==21.10"
        )

    # Runs a check each minute, but sends only when each user's 3-hour
    # deadline has arrived. A due reminder may be up to one minute late.
    application.job_queue.run_repeating(
        broadcast,
        interval=CHECK_INTERVAL_SECONDS,
        first=CHECK_INTERVAL_SECONDS,
        name="G168-SPORT-due-reminders",
    )
    logger.info("Bot started. User reminders repeat every 3 hours.")


def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing from Render Environment."
        )

    app = (
        ApplicationBuilder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    app.add_error_handler(on_error)

    start_health_server()
    logger.info("Starting G168-SPORT bot.")
    app.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
