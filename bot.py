
async def start(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
):
    message = update.effective_message
    user = update.effective_user

    if message is None or user is None:
        return

    now = time.time()

    # Check whether this user has used /start within 2 hours.
    with db_connection() as conn:
        row = conn.execute(
            "SELECT last_start FROM start_cooldowns WHERE user_id = ?",
            (user.id,),
        ).fetchone()

        if row is not None:
            elapsed = now - row[0]

            if elapsed < START_COOLDOWN_SECONDS:
                remaining = int(
                    START_COOLDOWN_SECONDS - elapsed
                )
                hours, remainder = divmod(remaining, 3600)
                minutes = (remainder + 59) // 60

                await message.reply_text(
                    "⏳ You have already started G168-SPORT.\n\n"
                    f"Please try again in about {hours}h "
                    f"{minutes}m."
                )
                return

        # Record the new start time.
        conn.execute("""
            INSERT INTO start_cooldowns (user_id, last_start)
            VALUES (?, ?)
            ON CONFLICT(user_id)
            DO UPDATE SET last_start = excluded.last_start
        """, (user.id, now))

    # Register the user for scheduled broadcasts.
    register_user(user.id)

    logger.info("Welcome cooldown accepted for user %s", user.id)

    # Send the original welcome image and message.
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
