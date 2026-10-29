import os
import logging
import asyncio
import random
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler
from apscheduler.schedulers.background import BackgroundScheduler

# បើកដំណើរការប្រព័ន្ធ Logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# ការកំណត់តេឡេក្រាមតូខន
TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")  

# អត្ថបទស្វាគមន៍ជាភាសាខ្មែរ
WELCOME_TEXT = """Wecome To 855GOAL
សូមស្វាគមន៍មកកាន់គេហទំព័រ 855GOAL ដែលជាគោលដៅដ៏ល្អបំផុតសម្រាប់អ្វីៗគ្រប់យ៉ាងដែលទាក់ទងនឹងការបង្កើនសមត្ថភាព និងការសម្រេចគោលដៅរបស់អ្នក។ សូមស្វែងយល់ពីធនធាន គន្លឹះ និងឧបករណ៍នានាដែលត្រូវបានរៀបចំឡើងដើម្បីផ្តល់ថាមពល និងការគាំទ្រដល់អ្នកនៅលើដំណើរឆ្ពោះទៅរកភាពជោគជ័យ។"""

# ប៊ូតុងតំណភ្ជាប់តាមទម្រង់រូបភាពដែលបានកំណត់ (DM NOW, WEBSITE, CHANNEL UPDATE)
reply_markup = InlineKeyboardMarkup([
    [InlineKeyboardButton("💬 DM NOW", url="https://t.me/GOALWIN855")],
    [InlineKeyboardButton("🌐 WEBSITE", url="https://heylink.me/855goal/")],
    [InlineKeyboardButton("📢 CHANNEL UPDATE", url="https://t.me/Game855GOAL")]
])

# បញ្ជីសារផ្សព្វផ្សាយទាក់ទាញជាភាសាខ្មែរសម្រាប់ផ្ញើស្វ័យប្រវត្តិរៀងរាល់ ៣ ម៉ោងម្តង (ប្តូរវេនគ្នា)
PROMO_MESSAGES_KH = [
    "🔥 ចុះឈ្មោះនៅលើគេហទំព័ររបស់យើងថ្ងៃនេះ ដើម្បីទទួលបានកាដូឥតគិតថ្លៃ ១០០$ ⭐️",
    "🎁 ចូលរួមជាមួយគេហទំព័រយើងថ្ងៃនេះ ហើយស្វែងរកប្រាក់រង្វាន់ឥតគិតថ្លៃជាច្រើន 🎁",
    "⭐ ចុះឈ្មោះឥឡូវនេះ ដើម្បីទទួលបានពិន្ទុប្រាក់រង្វាន់ ១០០$ ភ្លាមៗ ⭐️",
    "💰 តាមដានពួកเราគ្រប់បណ្តាញសង្គមទាំងអស់ ដើម្បីទទួលបានរង្វាន់ពិសេសៗខុសពីគេ 💰",
    "🎉 បង្កើតគណនីនៅលើគេហទំព័ររបស់យើងថ្ងៃនេះ ដើម្បីទទួលបានប្រាក់រង្វាន់ស្វាគមន៍ 🎉",
    "⭐️ ចុះឈ្មោះថ្ងៃនេះ បំពេញតាមលក្ខខណ្ឌ រួចรับផ្កាយរង្វាន់ដោយឥតគិតថ្លៃ ⭐️",
    "🎁 ចូលរួមក្នុងសហគមន៍យើង តាមដានទំព័ររបស់យើង និងទទួលបានប្រាក់រង្វាន់ពិសេសៗ 🎁",
    "🌟 ចុះឈ្មោះលើគេហទំព័រយើងថ្ងៃនេះ ថែមទាំងទទួលបានផ្កាយរង្វាន់ ១០០ ទៀតផង 🌟",
    "💸 តាមដានយើងគ្រប់ទីកន្លែង ចុះឈ្មោះលើគេហទំព័រយើងដើម្បីដោះសោរង្វាន់អស្ចារ្យជាច្រើន 💸",
    "⭐️ កុំឱ្យឱកាសនេះកន្លងផុត! ចុះឈ្មោះលើគេហទំព័រយើងថ្ងៃនេះដើម្បីទាមទារប្រាក់រង្វាន់ឥតគិតថ្លៃរបស់អ្នក ⭐️"
]

# បញ្ជីរក្សាទុក ID អ្នកប្រើប្រាស់ដែលបានចាប់ផ្តើម bot
active_users = set()

# បញ្ជីរូបភាព
IMAGE_FILES = [
    "images/image1.jpg",
    "images/image2.jpg",
    "images/image3.jpg",
    "images/image4.jpg",
    "images/image5.jpg",
    "images/image6.jpg"
]
current_image_index = 1  # ចាប់ផ្តើមរាប់ពីលេខ ១ សម្រាប់ពេលផ្ញើក្នុងរង្វង់ ៣ ម៉ោង

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    active_users.add(user_id)
    logger.info(f"អ្នកប្រើប្រាស់ថ្មីបានចាប់ផ្តើម Bot: {user_id}")

    # ផ្ញើរូបភាពទី១ ព្រមទាំងអត្ថបទស្វាគមន៍ និងប៊ូតុងតំណភ្ជាប់ (គ្មានអត្ថបទបញ្ជា /stop ទេ។)
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
        logger.info("មិនមានអ្នកប្រើប្រាស់សកម្មសម្រាប់ផ្ើសើសារទេ។")
        return

    image_path = IMAGE_FILES[current_image_index]
    
    # ជ្រើសរើសសារជាភាសាខ្មែរដោយចៃដន្យដើម្បីធ្វើបច្ចុប្បន្នភាពរៀងរាល់ ៣ ម៉ោង
    caption_text = f"🔥 **855GOAL Update**\n\n{random.choice(PROMO_MESSAGES_KH)}"

    logger.info(f"កំពុងផ្ញើរូបភាពលំដាប់ទី {current_image_index} ទៅកាន់អ្នកប្រើប្រាស់ចំនួន {len(active_users)} នាក់។")

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
            except Exception as e:
                logger.error(f"បរាជ័យក្នុងការផ្ញើសារទៅកាន់ {user_id}: {e}")
                active_users.discard(user_id)

    loop.run_until_complete(broadcast())
    loop.close()

    # ប្តូរទៅរូបភាពបន្ទាប់ និងរង្វិលត្រឡប់មកដើមវិញប្រសិនបើអស់ពីបញ្ជី
    current_image_index = (current_image_index + 1) % len(IMAGE_FILES)
    if current_image_index == 0:
        current_image_index = 1  # រំលងរូបភាពទី០ ក្នុងពេលផ្ញើស្វ័យប្រវត្តិរៀងរាល់ ៣ ម៉ោង

def main():
    if not TOKEN:
        logger.error("មិនទាន់បានកំណត់ Telegram Bot Token ទេ។")
        return

    application = ApplicationBuilder().token(TOKEN).build()

    # ចុះឈ្មោះ Command Handler សម្រាប់ /start
    application.add_handler(CommandHandler("start", start))

    # កំណត់កាលវិភាគស្វ័យប្រវត្តិរៀងរាល់ ៣ ម៉ោងម្តង
    scheduler = BackgroundScheduler()
    scheduler.add_job(send_scheduled_updates, 'interval', hours=3, args=[application])
    scheduler.start()

    logger.info("Bot កំពុងចាប់ផ្តើមដំណើរការហើយ...")
    application.run_polling()

if __name__ == "__main__":
    main()
