import os
import logging
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

# Handle Event Loop for Python 3.14+
try:
    asyncio.get_running_loop()
except RuntimeError:
    try:
        loop = asyncio.get_event_loop_policy().get_event_loop()
        if loop.is_closed():
            raise RuntimeError()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Telegram Bot Token environment variable
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  

# Welcome text in Khmer
WELCOME_TEXT = """Welcome To G168-SPORT

សូមស្វាគមន៍មកកាន់ G168-SPORT!

ទទួលបានព័ត៌មានកីឡា ព័ត៌មានបាល់ទាត់ លទ្ធផល និងព័ត៌មានថ្មីៗនៅទីនេះ។

សូមជ្រើសរើសជម្រើសខាងក្រោម 👇"""

# Inline keyboard buttons
reply_markup = InlineKeyboardMarkup([
    [InlineKeyboardButton("💬 DM NOW", url="https://t.me/GOALWIN855")],
    [InlineKeyboardButton("🌐 WEBSITE", url="https://heylink.me/855goal/")],
    [InlineKeyboardButton("📢 CHANNEL UPDATE", url="https://t.me/Game855GOAL")]
])

# Promotional messages in Khmer
PROMO_MESSAGES_KH = [
    "🔥 ចុះឈ្មោះនៅលើគេហទំព័ររបស់យើងថ្ងៃនេះ ដើម្បីទទួលបានកាដូឥតគិតថ្លៃ ១០០$ ⭐️",
    "🎁 ចូលរួមជាមួយគេហទំព័រយើងថ្ងៃនេះ ហើយស្វែងរកប្រាក់រង្វាន់ឥតគិតថ្លៃជាច្រើន 🎁",
    "⭐ ចុះឈ្មោះឥឡូវនេះ ដើម្បីទទួលបានពិន្ទុប្រាក់រង្វាន់ ១០០$ ភ្លាមៗ ⭐️",
    "💰 តាមដានពួកយើងគ្រប់បណ្តាញសង្គមទាំងអស់ ដើម្បីទទួលបានរង្វាន់ពិសេសៗខុសពីគេ 💰",
    "🎉 បង្កើតគណនីនៅលើគេហទំព័ររបស់យើងថ្ងៃនេះ ដើម្បីទទួលបានប្រាក់រង្វាន់ស្វាគមន៍ 🎉",
    "⭐️ ចុះឈ្មោះថ្ងៃនេះ បំពេញតាមលក្ខខណ្ឌ រួចទទួលបានផ្កាយរង្វាន់ដោយឥតគិតថ្លៃ ⭐️",
    "🎁 ចូលរួមក្នុងសហគមន៍យើង តាមដានទំព័ររបស់យើង និងទទួលបានប្រាក់រង្វាន់ពិសេសៗ 🎁",
    "🌟 ចុះឈ្មោះលើគេហទំព័រយើងថ្ងៃនេះ ថែមទាំងទទួលបានផ្កាយរង្វាន់ ១០០ ទៀតផង 🌟",
    "💸 តាមដានយើងគ្រប់ទីកន្លែង ចុះឈ្មោះលើគេហទំព័រយើងដើម្បីដោះសោរង្វាន់អស្ចារ្យជាច្រើន 💸",
    "⭐️ កុំឱ្យឱកាសនេះកន្លងផុត! ចុះឈ្មោះលើគេហទំព័រយើងថ្ងៃនេះដើម្បីទាមទារប្រាក់រង្វាន់ឥតគិតថ្លៃរបស់អ្នក ⭐️"
]

# Store active users
active_users = set()

# Image files list
IMAGE_FILES = [
    "images/image1.jpg",
    "images/image2.jpg",
    "images/image3.jpg",
    "images/image4.jpg",
    "images/image5.jpg",
    "images/image6.jpg"
]
current_image_index = 1

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    active_users.add(user_id)
    logger.info(f"New user started the bot: {user_id}")

    if os.path.exists(IMAGE_FILES[0]):
        with open(IMAGE_FILES[0], "rb") as photo:
            await update.message.reply_photo(
                photo=photo, 
                caption=WELCOME_TEXT, 
                reply_markup=reply_markup
            )
    else:
        await update.message.reply_text(
            text=WELCOME_TEXT, 
            reply_markup=reply_markup
        )

def send_scheduled_updates(application):
    global current_image_index
    if not active_users:
        logger.info("No active users to broadcast to.")
        return

    image_path = IMAGE_FILES[current_image_index]
    caption_text = f"🔥 **G168-SPORT Update**\n\n{random.choice(PROMO_MESSAGES_KH)}"

    logger.info(f"Broadcasting image index {current_image_index} to {len(active_users)} users.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def broadcast():
        for user_id in list(active_users):
            try:
                if os.path.exists(image_path):
                    with open(image_path, "rb") as photo:
                        await application.bot.send_photo(
                            chat_id=user_id, 
                            photo=photo, 
                            caption=caption_text, 
                            reply_markup=reply_markup,
                            parse_mode="Markdown"
                        )
                else:
                    await application.bot.send_message(
                        chat_id=user_id, 
                        text=caption_text, 
                        reply_markup=reply_markup
                    )
                # Small delay to prevent rate limits
                await asyncio.sleep(0.1)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
                active_users.discard(user_id)

    loop.run_until_complete(broadcast())
    loop.close()

    # Rotate to next image
    current_image_index = (current_image_index + 1) % len(IMAGE_FILES)
    if current_image_index == 0:
        current_image_index = 1

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    application = ApplicationBuilder().token(TOKEN).build()
    application.add_handler(CommandHandler("start", start))

    # Scheduled updates set to every 2 hours (hours=2)
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_scheduled_updates, 'interval', hours=2, args=[application])
    scheduler.start()

    logger.info("Bot is running and scheduled to send updates every 2 hours...")
    application.run_polling()

if __name__ == "__main__":
    main()
