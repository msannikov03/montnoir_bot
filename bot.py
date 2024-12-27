import logging
import os
import time
from dotenv import load_dotenv
from datetime import datetime
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.constants import ParseMode, ChatType
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler, MessageHandler, CallbackQueryHandler, filters
from telegram.helpers import mention_html
import psycopg2

load_dotenv()
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
SUPPORT_GROUP_ID = int(os.getenv("TELEGRAM_CHAT_ID"))
DATABASE_URL = os.getenv("DATABASE_URL")
SUPPORT_TEAM_IDS = [600911552, 1185876314, 706145083]
support_message_map = {}
user_language = {}
user_state = {}
user_messages = {}
last_seen_updated_at = None
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)
IMPORTANT_STATUSES = [
    "AUTHORIZED",
    "CONFIRMED",
    "PARTIAL_REFUNDED",
    "REFUNDED",
    "PARTIAL_REVERSED",
    "REVERSED",
    "REJECTED",
    "DEADLINE_EXPIRED"
]

def get_db_connection():
    return psycopg2.connect(DATABASE_URL)

def init_last_seen_updated_at():
    global last_seen_updated_at
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT MAX("updatedAt") FROM "Order"')
        row = cur.fetchone()
        if row and row[0]:
            last_seen_updated_at = row[0]
            logger.info(f"[DB Polling] Initial last_seen_updated_at set to {last_seen_updated_at}")
        else:
            logger.info("[DB Polling] No existing orders, starting fresh.")
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"init_last_seen_updated_at error: {e}", exc_info=True)

async def check_updated_orders(context: ContextTypes.DEFAULT_TYPE):
    global last_seen_updated_at
    if last_seen_updated_at is None:
        init_last_seen_updated_at()
        return
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        query = '''
            SELECT "id", "orderNumber", "firstName", "lastName",
                   "email", "phone", "address", "shippingMethod",
                   "subtotal", "total", "status", "createdAt", "items", "updatedAt", "coupons"
            FROM "Order"
            WHERE "updatedAt" > %s
            ORDER BY "updatedAt" ASC
        '''
        cur.execute(query, (last_seen_updated_at,))
        rows = cur.fetchall()
        col_names = [desc[0] for desc in cur.description]
        if rows:
            logger.info(f"[DB Polling] Found {len(rows)} updated order(s).")
        for row in rows:
            row_dict = dict(zip(col_names, row))
            order_id = row_dict["id"]
            order_status = row_dict["status"]
            order_updated_at = row_dict["updatedAt"]
            if order_status in IMPORTANT_STATUSES:
                message_text = (
                    f"🔔 <b>Order #{row_dict['orderNumber']} Status Update</b>\n"
                    f"<b>Name:</b> {row_dict['firstName']} {row_dict['lastName']}\n"
                    f"<b>Email:</b> {row_dict['email']}\n"
                    f"<b>Phone:</b> {row_dict['phone']}\n"
                    f"<b>Address:</b> {row_dict['address']}\n"
                    f"<b>Shipping:</b> {row_dict['shippingMethod']}\n"
                    f"<b>Subtotal:</b> {row_dict['subtotal']}\n"
                    f"<b>Total:</b> {row_dict['total']}\n"
                    f"<b>Status:</b> {row_dict['status']}\n"
                    f"<b>Ordered:</b> {row_dict['items']}\n"
                    f"<b>Created At:</b> {row_dict['createdAt']}\n"
                    f"<b>Updated At:</b> {row_dict['updatedAt']}\n"
                )
                coupons_value = row_dict.get("coupons")
                if coupons_value:
                    if isinstance(coupons_value, list):
                        coupons_str = ", ".join(coupons_value)
                    else:
                        coupons_str = str(coupons_value)
                    message_text += f"<b>Coupons:</b> {coupons_str}\n"
                await context.bot.send_message(chat_id=SUPPORT_GROUP_ID, text=message_text, parse_mode=ParseMode.HTML)
            if order_updated_at > last_seen_updated_at:
                last_seen_updated_at = order_updated_at
        cur.close()
        conn.close()
    except Exception as e:
        logger.error(f"[DB Polling] check_updated_orders error: {e}", exc_info=True)

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
        custom_keyboard = [[KeyboardButton("🌐 Website", web_app=WebAppInfo(url="https://montnoir.ru"))]]
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
        custom_keyboard = [[KeyboardButton("🌐 Сайт", web_app=WebAppInfo(url="https://montnoir.ru"))]]
        quick_access_text = "Быстрый доступ:"
    reply_markup = InlineKeyboardMarkup(buttons)
    custom_reply_markup = ReplyKeyboardMarkup(custom_keyboard, resize_keyboard=True, one_time_keyboard=False)
    if update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
        await update.message.reply_text(quick_access_text, reply_markup=custom_reply_markup)
    elif update.callback_query:
        await update.callback_query.message.reply_text(message_text, reply_markup=reply_markup)
        await update.callback_query.message.reply_text(quick_access_text, reply_markup=custom_reply_markup)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    button = [[InlineKeyboardButton(button_text, callback_data="send_support_request")]]
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
                await message.reply_text("Пожалуйста, отправьте текст или фото для поддержки.")
            return
        try:
            user_mention = mention_html(user.id, user.first_name or "User")
            support_message_text = "📩 <b>New Support Request</b>\n\n"
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
                await message.reply_text("✅ Your message has been forwarded to our support team.")
            else:
                await message.reply_text("✅ Ваше сообщение было отправлено в поддержку.")
        except Exception as e:
            logger.error("Error forwarding support message:", exc_info=e)
            if lang == "en":
                await message.reply_text("❌ Failed to forward your message. Please try again later.")
            else:
                await message.reply_text("❌ Не удалось отправить ваше сообщение. Пожалуйста, попробуйте позже.")
    else:
        if lang == "en":
            await message.reply_text("Use /support or the Support button to send a message.")
        else:
            await message.reply_text("Используйте /support или кнопку «Поддержка» для отправки сообщения.")

async def handle_support_reply(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    support_user = message.from_user
    if message.chat.id != SUPPORT_GROUP_ID:
        return
    if support_user.id not in SUPPORT_TEAM_IDS:
        await message.reply_text("❌ You are not authorized to send replies.")
        return
    if not message.reply_to_message:
        await message.reply_text("❌ Please reply to a specific support request message.")
        return
    original_message = message.reply_to_message
    user_id = support_message_map.get(original_message.message_id)
    if not user_id:
        await message.reply_text("❌ Could not find the original user for this message.")
        return
    try:
        if message.text:
            reply_content = f"📨 <b>Support Reply:</b>\n\n{message.text}"
            await context.bot.send_message(chat_id=user_id, text=reply_content, parse_mode=ParseMode.HTML)
        elif message.photo:
            caption_text = message.caption or "📷 Photo attached."
            reply_content = f"📨 <b>Support Reply:</b>\n\n{caption_text}"
            await context.bot.send_photo(chat_id=user_id, photo=message.photo[-1].file_id, caption=reply_content, parse_mode=ParseMode.HTML)
        else:
            reply_content = "📨 <b>Support Reply:</b>"
            await context.bot.send_message(chat_id=user_id, text=reply_content, parse_mode=ParseMode.HTML)
        await message.reply_text("✅ Reply sent to the user.")
    except Exception as e:
        logger.error("Error sending reply to user:", exc_info=e)
        await message.reply_text("❌ Failed to send the reply to the user.")

async def list_support_sessions(update: Update, context: ContextTypes.DEFAULT_TYPE):
    support_user = update.effective_user
    if support_user.id not in SUPPORT_TEAM_IDS:
        await update.message.reply_text("❌ You are not authorized to use this command.")
        return
    if not support_message_map:
        await update.message.reply_text("ℹ️ No active support sessions.")
        return
    support_list = "📋 <b>Active Support Sessions:</b>\n\n"
    for msg_id, uid in support_message_map.items():
        support_list += f"- <b>Message ID:</b> <code>{msg_id}</code> | <b>User ID:</b> <code>{uid}</code>\n"
    await update.message.reply_text(support_list, parse_mode=ParseMode.HTML)

async def unknown_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    lang = user_language.get(user_id, "ru")
    if lang == "en":
        await update.message.reply_text("❌ Unknown command. Please use /start to begin.")
    else:
        await update.message.reply_text("❌ Неизвестная команда. Пожалуйста, используйте /start для начала.")

def main():
    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("about", about))
    application.add_handler(CommandHandler("list", list_support_sessions))
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    application.add_handler(MessageHandler(filters.ChatType.PRIVATE & (filters.ALL & ~filters.COMMAND), handle_user_message))
    application.add_handler(MessageHandler((filters.Chat(SUPPORT_GROUP_ID)) & (filters.TEXT | filters.PHOTO) & filters.REPLY, handle_support_reply))
    application.add_handler(MessageHandler(filters.COMMAND, unknown_command))
    init_last_seen_updated_at()
    job_queue = application.job_queue
    job_queue.run_repeating(check_updated_orders, interval=10, first=5)
    logger.info("Bot is starting. Press Ctrl+C to stop.")
    application.run_polling()

if __name__ == "__main__":
    main()