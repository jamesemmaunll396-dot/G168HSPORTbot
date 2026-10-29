
import os
import logging
import asyncio
import random
import sqlite3
from pathlib import Path

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import Forbidden, TelegramError
from telegram.ext import (
    Application,
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
)

# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

INTERVAL_MINUTES = int(
    os.getenv("BROADCAST_INTERVAL_MINUTES", "120")
)

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "855goal_users.sqlite3"

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("G168-SPORT")

# ==================================================
# WELCOME MESSAGE AND BUTTONS
# ==================================================

WELCOME_TEXT = """Welcome To G168-SPORT

សូមស្វាគមន៍មកកាន់ G168-SPORT!

ទទួលបានព័ត៌មានកីឡា ព័ត៌មានបាល់ទាត់ លទ្ធផល និងព័ត៌មានថ្មីៗនៅទីយើង។

សូមជ្រើសរើសជម្រើសខាងក្រោម 👇"""

KEYBOARD = InlineKeyboardMarkup([
    [InlineKeyboardButton(
        "💬 DM NOW",
        url="https://t.me/GOALWIN855"
    )],
    [InlineKeyboardButton(
        "🌐 WEBSITE",
        url="https://heylink.me/855goal/"
    )],
    [InlineKeyboardButton(
        "📢 CHANNEL UPDATE",
        url="https://t.me/Game855GOAL"
    )],
])

# ==================================================
# IMAGE FILES
# Keep all six JPG files beside bot.py in GitHub.
# ==================================================

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

# ==================================================
# DATABASE
# ==================================================

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

    conn.commit()
    return conn


def register_user(user_id):
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO users (user_id, active)
            VALUES (?, 1)
            ON CONFLICT(user_id)
            DO UPDATE SET active = 1
        """, (user_id,))


def deactivate_user(user_id):
    with db_connection() as conn:
        conn.execute(
            "UPDATE users SET active = 0 WHERE user_id = ?",
            (user_id,),
        )


def list_active_users():
    with db_connection() as conn:
        rows = conn.execute(
            "SELECT user_id FROM users WHERE active = 1"
        ).fetchall()

    return [row[0] for row in rows]


def get_next_image():
    with db_connection() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE name = 'image_index'"
        ).fetchone()

        index = row[0] if row else 0
        following = (index + 1) % len(ROTATION_IMAGES)

        conn.execute("""
            INSERT INTO settings (name, value)
            VALUES ('image_index', ?)
            ON CONFLICT(name)
            DO UPDATE SET value = excluded.value
        """, (following,))

    return ROTATION_IMAGES[index]


# ==================================================
# /START — SEND WELCOME IMAGE IMMEDIATELY
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if message is None or user is None:
        return

    register_user(user.id)
    logger.info("User registered: %s", user.id)

    if not WELCOME_IMAGE.is_file():
        logger.error("Welcome image not found: %s", WELCOME_IMAGE)
        await message.reply_text(
            WELCOME_TEXT,
            reply_markup=KEYBOARD,
        )
        return

    try:
        with WELCOME_IMAGE.open("rb") as photo:
            await message.reply_photo(
                photo=photo,
                caption=WELCOME_TEXT,
                reply_markup=KEYBOARD,
            )
    except TelegramError:
        logger.exception("Failed to send welcome image")
        await message.reply_text(
            WELCOME_TEXT,
            reply_markup=KEYBOARD,
        )


# ==================================================
# /STOP — STOP AUTOMATIC MESSAGES
# ==================================================

async def stop(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    user = update.effective_user
    message = update.effective_message

    if user:
        deactivate_user(user.id)

    if message:
        await message.reply_text(
            "Automatic updates stopped. Send /start to subscribe again."
        )


# ==================================================
# /STATUS — CHECK BOT STATUS
# ==================================================

async def status(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message

    if message:
        await message.reply_text(
            "✅ G168-SPORT bot is running.\n"
            f"Broadcast interval: {INTERVAL_MINUTES} minutes.\n"
            f"Active subscribers: {len(list_active_users())}."
        )


# ==================================================
# AUTOMATIC IMAGE BROADCAST
# ==================================================

async def broadcast(
    context: ContextTypes.DEFAULT_TYPE,
):
    users = list_active_users()

    if not users:
        logger.info("No active subscribers; skipping broadcast.")
        return

    image_path = get_next_image()

    if not image_path.is_file():
        logger.error("Scheduled image not found: %s", image_path)
        return

    caption = (
        "⚽ G168-SPORT Update\n\n"
        + random.choice(PROMO_MESSAGES_KH)
        + "\n\n🌐 Website: https://heylink.me/855goal/"
        + "\n📢 Channel: https://t.me/Game855GOAL"
    )

    sent = 0
    logger.info(
        "Broadcasting %s to %d subscribers",
        image_path.name,
        len(users),
    )

    for user_id in users:
        try:
            with image_path.open("rb") as photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=KEYBOARD,
                )

            sent += 1
            await asyncio.sleep(0.05)

        except Forbidden:
            deactivate_user(user_id)
            logger.info("User blocked bot; deactivated: %s", user_id)

        except TelegramError:
            logger.exception("Failed sending to user %s", user_id)

    logger.info("Broadcast complete: %d/%d delivered", sent, len(users))


# ==================================================
# APPLICATION STARTUP
# ==================================================

async def post_init(application: Application):
    with db_connection():
        pass

    all_images = [WELCOME_IMAGE, *ROTATION_IMAGES]
    missing = [str(p.name) for p in all_images if not p.is_file()]

    if missing:
        logger.error("Missing image files: %s", ", ".join(missing))

    if INTERVAL_MINUTES < 1:
        raise ValueError("BROADCAST_INTERVAL_MINUTES", "180")

    if application.job_queue is None:
        raise RuntimeError(
            "Job queue is unavailable. Install "
            "python-telegram-bot[job-queue]==21.10"
        )

    application.job_queue.run_repeating(
        broadcast,
        interval=INTERVAL_MINUTES * 60,
        first=INTERVAL_MINUTES * 60,
        name="G168-SPORT-broadcast",
    )

    logger.info(
        "Bot initialized; broadcasts scheduled every %d minutes.",
        INTERVAL_MINUTES,
    )


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

    logger.info("Starting G168-SPORT bot.")
    app.run_polling()


if __name__ == "__main__":
    try:
        asyncio.get_event_loop()
    except RuntimeError:
        asyncio.set_event_loop(asyncio.new_event_loop())

    main()
