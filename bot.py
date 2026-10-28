
import logging
import os
import sqlite3
import asyncio
from pathlib import Path

from telegram import Update
from telegram.error import Forbidden, TelegramError, RetryAfter
from telegram.ext import Application, CommandHandler, ContextTypes

# ================ CONFIGURATION ================

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BROADCAST_INTERVAL_MINUTES = int(
    os.getenv("BROADCAST_INTERVAL_MINUTES", "4")
)

BASE_DIR = Path(__file__).resolve().parent

# Image files shown in your GitHub screenshot.
# Keep all six files beside bot.py in the repository root.
IMAGE_FILES = [
    BASE_DIR / "5985379721660800808.jpg",
    BASE_DIR / "5985379721660800809.jpg",
    BASE_DIR / "5985379721660800810.jpg",
    BASE_DIR / "5985379721660800811.jpg",
    BASE_DIR / "5985379721660800812.jpg",
    BASE_DIR / "5985379721660800813.jpg",
]

WEBSITE_URL = "https://heylink.me/855goal/"
CHANNEL_URL = "https://t.me/Game855GOAL"
SUPPORT_URL = "https://t.me/GOALWIN855"

WELCOME_TEXT = f"""Welcome To 855GOAL

សូមស្វាគមន៍មកកាន់គេហទំព័រ 855GOAL ដែលជាគោលដៅដ៏ល្អបំផុតសម្រាប់អ្វីៗគ្រប់យ៉ាងដែលទាក់ទងនឹងការបង្កើនសមត្ថភាព និងការសម្រេចគោលដៅរបស់អ្នក។ សូមស្វែងយល់ពីធនធាន គន្លឹះ និងឧបករណ៍នានាដែលត្រូវបានរៀបចំឡើងដើម្បីផ្តល់ថាមពល និងការគាំទ្រដល់អ្នកនៅលើដំណើរឆ្ពោះទៅរកភាពជោគជ័យ។

🌐 Website: {WEBSITE_URL}
📢 Channel: {CHANNEL_URL}
💬 Contact: {SUPPORT_URL}

Send /stop to stop automatic messages."""

# Replace these temporary descriptions with descriptions
# that accurately match each of your six images.
IMAGE_DESCRIPTIONS = [
    "Welcome to 855GOAL.",
    "855GOAL update — image 2.",
    "855GOAL update — image 3.",
    "855GOAL update — image 4.",
    "855GOAL update — image 5.",
    "855GOAL update — image 6.",
]

# Set DATA_DIR to a persistent Render disk mount if available.
DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR)))
DATA_DIR.mkdir(parents=True, exist_ok=True)
DB_PATH = DATA_DIR / "855goal_users.sqlite3"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger("855goal")


# ================ DATABASE ================

def db_connect():
    return sqlite3.connect(DB_PATH, timeout=30)


def init_db():
    with db_connect() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS subscribers (
                user_id INTEGER PRIMARY KEY,
                active INTEGER NOT NULL DEFAULT 1,
                joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                setting_key TEXT PRIMARY KEY,
                setting_value TEXT NOT NULL
            )
        """)
        conn.execute("""
            INSERT OR IGNORE INTO settings
            (setting_key, setting_value)
            VALUES ('next_image_index', '1')
        """)
    logger.info("Database ready: %s", DB_PATH)


def subscribe(user_id):
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO subscribers (user_id, active)
            VALUES (?, 1)
            ON CONFLICT(user_id) DO UPDATE SET active = 1
        """, (user_id,))


def unsubscribe(user_id):
    with db_connect() as conn:
        conn.execute(
            "UPDATE subscribers SET active = 0 WHERE user_id = ?",
            (user_id,),
        )


def active_subscribers():
    with db_connect() as conn:
        rows = conn.execute(
            "SELECT user_id FROM subscribers WHERE active = 1"
        ).fetchall()
    return [row[0] for row in rows]


def next_image_index():
    with db_connect() as conn:
        row = conn.execute(
            "SELECT setting_value FROM settings "
            "WHERE setting_key = 'next_image_index'"
        ).fetchone()
    return int(row[0]) if row else 1


def save_next_image_index(index):
    with db_connect() as conn:
        conn.execute("""
            INSERT INTO settings (setting_key, setting_value)
            VALUES ('next_image_index', ?)
            ON CONFLICT(setting_key)
            DO UPDATE SET setting_value = excluded.setting_value
        """, (str(index),))


# ================ MESSAGES ================

def image_caption(index):
    return (
        f"Welcome To 855GOAL\n\n"
        f"{IMAGE_DESCRIPTIONS[index]}\n\n"
        f"🌐 Website: {WEBSITE_URL}\n"
        f"📢 Channel: {CHANNEL_URL}\n"
        f"💬 Contact: {SUPPORT_URL}\n\n"
        f"Send /stop to stop automatic messages."
    )


async def send_image(bot, chat_id, index):
    path = IMAGE_FILES[index]

    if not path.is_file():
        raise FileNotFoundError(
            f"Missing image: {path.name}. Check your GitHub files."
        )

    caption = WELCOME_TEXT if index == 0 else image_caption(index)

    with path.open("rb") as photo:
        await bot.send_photo(
            chat_id=chat_id,
            photo=photo,
            caption=caption,
        )


# ================ BOT COMMANDS ================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    message = update.effective_message

    if not user or not message:
        return

    subscribe(user.id)
    logger.info("User subscribed: %s", user.id)

    try:
        await send_image(context.bot, user.id, 0)
    except (TelegramError, OSError):
        logger.exception("Welcome image failed for %s", user.id)
        await message.reply_text(
            "Welcome to 855GOAL! Your subscription is saved, "
            "but the welcome image could not be sent. Please try again."
        )


async def stop(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    if user:
        unsubscribe(user.id)
        logger.info("User unsubscribed: %s", user.id)

    if update.effective_message:
        await update.effective_message.reply_text(
            "Automatic messages stopped. Send /start to subscribe again."
        )


async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_message:
        await update.effective_message.reply_text(
            "855GOAL bot is running.\n"
            f"Broadcast interval: {BROADCAST_INTERVAL_MINUTES} minutes.\n"
            "Use /stop to stop scheduled messages."
        )


# ================ SCHEDULED BROADCAST ================

async def broadcast(context: ContextTypes.DEFAULT_TYPE):
    users = active_subscribers()

    if not users:
        logger.info("No subscribers; skipping broadcast.")
        return

    # Image 1 is reserved for /start.
    # Scheduled broadcasts rotate through images 2 to 6.
    index = next_image_index()

    if index < 1 or index >= len(IMAGE_FILES):
        index = 1

    logger.info(
        "Broadcasting image %s to %s users",
        index + 1,
        len(users),
    )

    sent = 0
    failed = 0

    for user_id in users:
        try:
            await send_image(context.bot, user_id, index)
            sent += 1

        except RetryAfter as exc:
            wait_seconds = int(exc.retry_after) + 1
            logger.warning(
                "Rate limit reached; waiting %s seconds",
                wait_seconds,
            )
            await asyncio.sleep(wait_seconds)

            try:
                await send_image(context.bot, user_id, index)
                sent += 1
            except TelegramError:
                failed += 1
                logger.exception("Retry failed for %s", user_id)

        except Forbidden:
            # A blocked bot cannot message this user.
            unsubscribe(user_id)
            failed += 1
            logger.info("Unsubscribed unavailable user: %s", user_id)

        except (TelegramError, OSError):
            failed += 1
            logger.exception("Sending failed for %s", user_id)

    # Advance to the next scheduled image.
    next_index = index + 1
    if next_index >= len(IMAGE_FILES):
        next_index = 1

    save_next_image_index(next_index)

    logger.info("Broadcast finished: sent=%s failed=%s", sent, failed)


async def post_init(application: Application):
    init_db()

    for path in IMAGE_FILES:
        if not path.is_file():
            logger.error("Image missing from repository: %s", path.name)

    if application.job_queue is None:
        raise RuntimeError(
            "JobQueue unavailable. Check requirements.txt."
        )

    application.job_queue.run_repeating(
        broadcast,
        interval=BROADCAST_INTERVAL_MINUTES * 60,
        first=BROADCAST_INTERVAL_MINUTES * 60,
        name="855goal-broadcast",
    )

    logger.info(
        "Scheduled broadcasts every %s minutes",
        BROADCAST_INTERVAL_MINUTES,
    )


# ================ START BOT ================

def main():
    if not TOKEN:
        raise RuntimeError(
            "TELEGRAM_BOT_TOKEN is missing. "
            "Add it in Render > Environment."
        )

    app = (
        Application.builder()
        .token(TOKEN)
        .post_init(post_init)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("stop", stop))
    app.add_handler(CommandHandler("status", status))

    logger.info("Starting 855GOAL bot.")
    app.run_polling()



if __name__ == "__main__":
    asyncio.set_event_loop(asyncio.new_event_loop())
    main()
