import os
import logging
import asyncio
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  # Set this in Render Environment Variables

WELCOME_TEXT = """Wecome To 855GOAL
សូមស្វាគមន៍មកកាន់គេហទំព័រ 855GOAL ដែលជាគោលដៅដ៏ល្អបំផុតសម្រាប់អ្វីៗគ្រប់យ៉ាងដែលទាក់ទងនឹងការបង្កើនសមត្ថភាព និងការសម្រេចគោលដៅរបស់អ្នក។ សូមស្វែងយល់ពីធនធាន គន្លឹះ និងឧបករណ៍នានាដែលត្រូវបានរៀបចំឡើងដើម្បីផ្តល់ថាមពល និងការគាំទ្រដល់អ្នកនៅលើដំណើរឆ្ពោះទៅរកភាពជោគជ័យ។

🔗 Website: https://heylink.me/855goal/
📢 Channel: https://t.me/Game855GOAL
💬 Support: https://t.me/GOALWIN855"""

# Store user IDs who started the bot (in-memory storage; use a database for production persistence)
active_users = set()

# List of images and index tracker
IMAGE_FILES = [
    "images/image1.jpg",
    "images/image2.jpg",
    "images/image3.jpg",
    "images/image4.jpg",
    "images/image5.jpg",
    "images/image6.jpg"
]
current_image_index = 1  # Start from index 1 for the 3-hour loop (index 0 is for welcome)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    active_users.add(user_id)
    logger.info(f"New user started the bot: {user_id}")

    # Send first image with welcome text
    if os.path.exists(IMAGE_FILES[0]):
        with open(IMAGE_FILES[0], "rb") as photo:
            await update.message.render_photo(photo=photo, caption=WELCOME_TEXT)
    else:
        await update.message.reply_text(WELCOME_TEXT)

def send_scheduled_updates(application):
    global current_image_index
    if not active_users:
        logger.info("No active users to broadcast to.")
        return

    image_path = IMAGE_FILES[current_image_index]
    caption_text = f"🔥 **855GOAL Update**\n\nCheck out our latest offers and games!\n\n🔗 https://heylink.me/855goal/"

    logger.info(f"Broadcasting image index {current_image_index} to {len(active_users)} users.")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    async def broadcast():
        for user_id in list(active_users):
            try:
                if os.path.exists(image_path):
                    with open(image_path, "rb") as photo:
                        await application.bot.send_photo(chat_id=user_id, photo=photo, caption=caption_text, parse_mode="Markdown")
                else:
                    await application.bot.send_message(chat_id=user_id, text=caption_text)
            except Exception as e:
                logger.error(f"Failed to send message to {user_id}: {e}")
                # Remove blocked or inactive users
                active_users.discard(user_id)

    loop.run_until_complete(broadcast())
    loop.close()

    # Rotate to the next image, loop back if reaching the end
    current_image_index = (current_image_index + 1) % len(IMAGE_FILES)
    if current_image_index == 0:
        current_image_index = 1  # Skip index 0 (welcome image) in the regular cycle

def main():
    if not TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN environment variable not set!")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    # Register command handler
    application.add_handler(CommandHandler("start", start))

    # Setup Background Scheduler for every 3 hours
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_scheduled_updates, 'interval', hours=3, args=[application])
    scheduler.start()

    logger.info("Bot is starting polling and scheduler...")
    application.run_polling()

if __name__ == "__main__":
    main()
