
import os
import logging
import asyncio
import random
import sqlite3
from pathlib import Path

# ==================================================
# CONFIGURATION
# ==================================================

BASE_DIR = Path(__file__).resolve().parent
TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

# Send automatic reminders every 2 hours
INTERVAL_MINUTES = int(
    os.getenv("BROADCAST_INTERVAL_MINUTES", "120")
)
