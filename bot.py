import logging
import os
from telegram import (
    Update,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    ReplyKeyboardMarkup,
    KeyboardButton,
    WebAppInfo,
)
from telegram.constants import ParseMode, ChatType
from telegram.ext import (
    ApplicationBuilder,
    ContextTypes,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
)
from telegram.helpers import mention_html

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

SUPPORT_GROUP_ID = os.getenv("SUPPORT_GROUP_ID")

SUPPORT_TEAM_IDS = os.getenv("SUPPORT_TEAM_IDS")

support_message_map = {}

user_language = {}
user_state = {}

user_messages = {}

async def send_start_message(update: Update, context: ContextTypes.DEFAULT_TYPE, lang="ru"):
    user = update.effective_user
    if lang == "en":
        message_text = (
            f"Hello {user.first_name}! Welcome to the Support Bot.\n\n"
            "Click the buttons below to visit the website, contact support, or learn more about this bot."
        )
        buttons = [
            [
                InlineKeyboardButton("🌐 Website", url="https://montnoir.ru"),
                InlineKeyboardButton("🇷🇺 Русский", callback_data="language_ru"),
            ],
            [
                InlineKeyboardButton("Support", callback_data="support"),
                InlineKeyboardButton("About", callback_data="about"),
            ],
        ]
        custom_keyboard = [
            [KeyboardButton("🌐 Website", web_app=WebAppInfo(url="https://montnoir.ru"))]
        ]
        quick_access_text = "Quick access:"
    else:
        message_text = (
            f"Привет {user.first_name}! Добро пожаловать в бот поддержки.\n\n"
            "Нажмите на кнопки ниже, чтобы посетить сайт, узнать о поддержке или узнать, зачем нужен этот бот."
        )
        buttons = [
            [
                InlineKeyboardButton("🌐 Сайт", url="https://montnoir.ru"),
                InlineKeyboardButton("🇬🇧 English", callback_data="language_en"),
            ],
            [
                InlineKeyboardButton("Поддержка", callback_data="support"),
                InlineKeyboardButton("Что это?", callback_data="about"),
            ],
        ]
        custom_keyboard = [
            [KeyboardButton("🌐 Сайт", web_app=WebAppInfo(url="https://montnoir.ru"))]
        ]
        quick_access_text = "Быстрый доступ:"

    reply_markup = InlineKeyboardMarkup(buttons)
    custom_reply_markup = ReplyKeyboardMarkup(
        custom_keyboard, resize_keyboard=True, one_time_keyboard=False
    )

    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
        await update.message.reply_text(
            quick_access_text, reply_markup=custom_reply_markup
        )
    elif update.callback_query:
        await update.callback_query.message.reply_text(
            message_text, reply_markup=reply_markup
        )
        await update.callback_query.message.reply_text(
            quick_access_text, reply_markup=custom_reply_markup
        )

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles the /start command."""
    user_language[update.effective_user.id] = "ru"
    await send_start_message(update, context, "ru")

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ru")
    if lang == "en":
        msg_text = "To contact support, please click the button below."
        button_text = "Send Support Request"
    else:
        msg_text = "Чтобы обратиться в службу поддержки, нажмите кнопку ниже."
        button_text = "Отправить сообщение в поддержку"

    button = [
        [InlineKeyboardButton(button_text, callback_data="send_support_request")]
    ]
    reply_markup = InlineKeyboardMarkup(button)

    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(msg_text, reply_markup=reply_markup)

async def about(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ru")
    if lang == "en":
        message_text = (
            "Welcome to the Telegram version of our store. In this bot, you can find out how to contact support "
            "or open our website directly in Telegram. To launch the site, click the 'Website' button in the "
            "first message. To contact support, click the 'Support' button or send the /support command."
        )
    else:
        message_text = (
            "Добро пожаловать в Телеграм-версию нашего магазина. В этом боте вы можете узнать, как связаться "
            "с поддержкой, или открыть наш сайт прямо в Телеграм. Чтобы запустить сайт, нажмите кнопку «Сайт» "
            "в первом сообщении. Чтобы связаться с поддержкой, нажмите на кнопку «Поддержка» или отправьте "
            "команду /support в чат."
        )
    if update.callback_query:
        await update.callback_query.message.reply_text(message_text)
    else:
        await update.message.reply_text(message_text)

async def prompt_support_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ru")
    if lang == "en":
        msg_text = "Please write your support message."
    else:
        msg_text = "Пожалуйста, напишите ваше сообщение в поддержку."
    if update.callback_query:
        await update.callback_query.message.reply_text(msg_text)
    else:
        await update.message.reply_text(msg_text)
    user_state[user_id] = 'awaiting_support_message'

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id

    if query.data == "language_en":
        user_language[user_id] = "en"
        await send_start_message(update, context, "en")
    elif query.data == "language_ru":
        user_language[user_id] = "ru"
        await send_start_message(update, context, "ru")
    elif query.data == "support":
        await support(update, context)
    elif query.data == "about":
        await about(update, context)
    elif query.data == "send_support_request":
        await prompt_support_message(update, context)

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles incoming text and photo messages from users and forwards them to the support group."""
    user = update.effective_user
    message = update.message

    if message.chat.type != ChatType.PRIVATE:
        return

    user_id = user.id
    lang = user_language.get(user_id, "ru")
    state = user_state.get(user_id)

    if state == 'awaiting_support_message':
        if not (message.text or message.photo):
            if lang == "en":
                await message.reply_text("Please send text or photo messages for support.")
            else:
                await message.reply_text("Пожалуйста, отправьте текстовое сообщение или фотографию для поддержки.")
            return

        try:
            user_mention = mention_html(user.id, user.first_name or "User")
            support_message_text = f"📩 <b>New Support Request</b>\n\n"
            support_message_text += f"<b>From:</b> {user_mention}"
            if user.username:
                support_message_text += f" (@{user.username})"
            support_message_text += f"\n<b>User ID:</b> <code>{user.id}</code>"

            if message.text:
                support_message_text += f"\n<b>Message:</b> {message.text}"
                forwarded_message = await context.bot.send_message(
                    chat_id=SUPPORT_GROUP_ID,
                    text=support_message_text,
                    parse_mode=ParseMode.HTML,
                )
            elif message.photo:
                caption_text = message.caption or "📷 Photo attached."
                support_message_text += f"\n<b>Message:</b> {caption_text}"
                forwarded_message = await context.bot.send_photo(
                    chat_id=SUPPORT_GROUP_ID,
                    photo=message.photo[-1].file_id,
                    caption=support_message_text,
                    parse_mode=ParseMode.HTML,
                )

            support_message_map[forwarded_message.message_id] = user.id

            user_state[user_id] = None
            if lang == "en":
                await message.reply_text(
                    "✅ Your message has been forwarded to our support team. We'll get back to you shortly."
                )
            else:
                await message.reply_text(
                    "✅ Ваше сообщение было отправлено в поддержку. Мы свяжемся с вами в ближайшее время."
                )

        except Exception as e:
            if lang == "en":
                await message.reply_text(
                    "❌ Failed to forward your message. Please try again later."
                )
            else:
                await message.reply_text(
                    "❌ Не удалось отправить ваше сообщение. Пожалуйста, попробуйте позже."
                )
    else:
        if lang == "en":
            await message.reply_text(
                "Please use the /support command or press the Support button to send a message to support."
            )
        else:
            await message.reply_text(
                "Пожалуйста, используйте команду /support или нажмите кнопку «Поддержка», чтобы отправить сообщение в поддержку."
            )

async def handle_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles replies from the support group and sends them back to the respective users."""
    message = update.message
    support_user = message.from_user

    if message.chat.id != SUPPORT_GROUP_ID:
        return

    if support_user.id not in SUPPORT_TEAM_IDS:
        await message.reply_text("❌ You are not authorized to send replies.")
        return

    if not message.reply_to_message:
        await message.reply_text(
            "❌ Please reply to a specific support request message."
        )
        return

    original_message = message.reply_to_message

    user_id = support_message_map.get(original_message.message_id)

    if not user_id:
        await message.reply_text(
            "❌ Could not find the original user for this message."
        )
        return

    lang = user_language.get(user_id, "ru")

    try:
        if message.text:
            reply_content = f"📨 <b>Support Reply:</b>\n\n{message.text}"
            await context.bot.send_message(
                chat_id=user_id,
                text=reply_content,
                parse_mode=ParseMode.HTML,
            )
        elif message.photo:
            caption_text = message.caption or "📷 Photo attached."
            reply_content = f"📨 <b>Support Reply:</b>\n\n{caption_text}"
            await context.bot.send_photo(
                chat_id=user_id,
                photo=message.photo[-1].file_id,
                caption=reply_content,
                parse_mode=ParseMode.HTML,
            )
        else:
            reply_content = "📨 <b>Support Reply:</b>"
            await context.bot.send_message(
                chat_id=user_id,
                text=reply_content,
                parse_mode=ParseMode.HTML,
            )

        await message.reply_text("✅ Reply sent to the user.")
    except Exception as e:
        await message.reply_text("❌ Failed to send the reply to the user.")

async def list_support_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Lists all active support sessions."""
    support_user = update.effective_user

    if support_user.id not in SUPPORT_TEAM_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return

    if not support_message_map:
        await update.message.reply_text("ℹ️ No active support sessions.")
        return

    support_list = "📋 <b>Active Support Sessions:</b>\n\n"
    for msg_id, user_id in support_message_map.items():
        support_list += f"- <b>Message ID:</b> <code>{msg_id}</code> | <b>User ID:</b> <code>{user_id}</code>\n"

    await update.message.reply_text(support_list, parse_mode=ParseMode.HTML)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handles unknown commands."""
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ru")
    if lang == "en":
        await update.message.reply_text("❌ Unknown command. Please use /start to begin.")
    else:
        await update.message.reply_text("❌ Неизвестная команда. Пожалуйста, используйте /start для начала.")

def main():
    """Starts the bot."""
    application = ApplicationBuilder().token(BOT_TOKEN).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("list", list_support_sessions))

    application.add_handler(CallbackQueryHandler(handle_callback_query))

    application.add_handler(
        MessageHandler(
            filters.ChatType.PRIVATE & (filters.ALL & ~filters.COMMAND),
            handle_user_message,
        )
    )

    application.add_handler(
        MessageHandler(
            (filters.Chat(SUPPORT_GROUP_ID))
            & (filters.TEXT | filters.PHOTO)
            & filters.REPLY,
            handle_support_reply,
        )
    )

    application.add_handler(
        MessageHandler(filters.COMMAND, unknown_command)
    ) 

    application.run_polling()

if __name__ == "__main__":
    main()