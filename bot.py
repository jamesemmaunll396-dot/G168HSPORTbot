
import os
import logging
import asyncio
import random
import sqlite3
import time
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

# Send the first automatic message 2 hours after /start,
# then repeat every 2 hours.
START_DELAY_SECONDS = 2 * 60 * 60
BROADCAST_INTERVAL_SECONDS = 2 * 60 * 60

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "855goal_users.sqlite3"

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger("G168-SPORT")

# ==================================================
# ORIGINAL WELCOME MESSAGE
# ==================================================

WELCOME_TEXT = """Welcome To G168-SPORT

សូមស្វាគមន៍មកកាន់ G168-SPORT!

ទទួលបានព័ត៌មានកីឡា ព័ត៌មានបាល់ទាត់ លទ្ធផល និងព័ត៌មានថ្មីៗនៅទីយើង។

សូមជ្រើសរើសជម្រើសខាងក្រោម 👇"""

# ==================================================
# ORIGINAL BUTTONS
# ==================================================

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
# ORIGINAL IMAGE FILES
# Keep all JPG files beside bot.py.
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

    # Remember when each user last received the welcome message.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS start_cooldowns (
            user_id INTEGER PRIMARY KEY,
            last_start REAL NOT NULL
        )
    """)

    # Remember each user's scheduled reminder time.
    conn.execute("""
        CREATE TABLE IF NOT EXISTS user_schedules (
            user_id INTEGER PRIMARY KEY,
            next_send REAL NOT NULL
        )
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

        index = (row[0] if row else 0) % len(ROTATION_IMAGES)
        following = (index + 1) % len(ROTATION_IMAGES)

        conn.execute("""
            INSERT INTO settings (name, value)
            VALUES ('image_index', ?)
            ON CONFLICT(name)
            DO UPDATE SET value = excluded.value
        """, (following,))

    return ROTATION_IMAGES[index]


def welcome_cooldown_remaining(user_id, now):
    with db_connection() as conn:
        row = conn.execute(
            "SELECT last_start FROM start_cooldowns WHERE user_id = ?",
            (user_id,),
        ).fetchone()

    if row is None:
        return 0

    remaining = START_DELAY_SECONDS - (now - row[0])
    return max(0, int(remaining))


def record_start_and_schedule(user_id, now):
    with db_connection() as conn:
        conn.execute("""
            INSERT INTO start_cooldowns (user_id, last_start)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET last_start = excluded.last_start
        """, (user_id, now))

        conn.execute("""
            INSERT INTO user_schedules (user_id, next_send)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET next_send = excluded.next_send
        """, (user_id, now + START_DELAY_SECONDS))


# ==================================================
# /START — WELCOME IMAGE IMMEDIATELY
# ==================================================

async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
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

    logger.info("Welcome sent/scheduled for user %s", user.id)

    if not WELCOME_IMAGE.is_file():
        logger.error("Welcome image missing: %s", WELCOME_IMAGE)
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

        with db_connection() as conn:
            conn.execute(
                "DELETE FROM user_schedules WHERE user_id = ?",
                (user.id,),
            )

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
            "First automatic reminder: 2 hours after /start.\n"
            "Repeat interval: every 2 hours.\n"
            f"Active subscribers: {len(list_active_users())}."
        )


# ==================================================
# AUTOMATIC IMAGE BROADCAST
# Send only to users whose reminder is due.
# ==================================================

async def broadcast(context: ContextTypes.DEFAULT_TYPE):
    now = time.time()

    with db_connection() as conn:
        rows = conn.execute("""
            SELECT s.user_id
            FROM user_schedules s
            JOIN users u ON u.user_id = s.user_id
            WHERE u.active = 1 AND s.next_send <= ?
        """, (now,)).fetchall()

    due_users = [row[0] for row in rows]

    if not due_users:
        logger.info("No reminders due yet.")
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

    for user_id in due_users:
        try:
            with image_path.open("rb") as photo:
                await context.bot.send_photo(
                    chat_id=user_id,
                    photo=photo,
                    caption=caption,
                    reply_markup=KEYBOARD,
                )

            # Schedule this user's next message 2 hours later.
            with db_connection() as conn:
                conn.execute("""
                    UPDATE user_schedules
                    SET next_send = ?
                    WHERE user_id = ?
                """, (time.time() + BROADCAST_INTERVAL_SECONDS, user_id))

            await asyncio.sleep(0.05)

        except Forbidden:
            deactivate_user(user_id)
            logger.info("User blocked bot: %s", user_id)

        except TelegramError:
            logger.exception("Failed sending to user %s", user_id)


# ==================================================
# APPLICATION STARTUP
# ==================================================

async def post_init(application: Application):
    with db_connection():
        pass

    all_images = [WELCOME_IMAGE, *ROTATION_IMAGES]
    missing = [p.name for p in all_images if not p.is_file()]

    if missing:
        logger.warning("Missing image files: %s", ", ".join(missing))

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue unavailable. Install "
            "python-telegram-bot[job-queue]==21.10"
        )

    # Check every minute for users whose 2-hour reminder is due.
    # This check frequency does NOT mean messages are sent every minute.
    application.job_queue.run_repeating(
        broadcast,
        interval=60,
        first=60,
        name="G168-SPORT-due-reminders",
    )

    logger.info(
        "Bot started. User reminders are scheduled 2 hours apart."
    )


# ==================================================
# RUN BOT
# ==================================================

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
    main()
