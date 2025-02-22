from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, CallbackContext, CallbackQueryHandler
import json
import os
import logging
import pytz
import asyncio
import nest_asyncio
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from datetime import datetime, timedelta

# Enable logging
logging.basicConfig(format='%(asctime)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

# Load or create file metadata storage
DATA_FILE = "file_metadata.json"
USER_PREFS_FILE = "user_preferences.json"
USER_SESSION = {}
ADMIN_ID = 123456789  # Replace with actual admin ID

if os.path.exists(DATA_FILE):
    with open(DATA_FILE, "r") as f:
        file_metadata = json.load(f)
else:
    file_metadata = {}

if os.path.exists(USER_PREFS_FILE):
    with open(USER_PREFS_FILE, "r") as f:
        user_preferences = json.load(f)
else:
    user_preferences = {}

# Replace with your actual bot token from BotFather
TOKEN = "7664267704:AAGW7jH6CD3iWinYWLmpqHASp7AcAnWl0A0"

async def start(update: Update, context: CallbackContext):
    user = update.message.from_user
    chat = update.message.chat
    
    welcome_message = f"Hello {user.first_name}, welcome to {chat.title}! Here are the available services:"
    services = [[InlineKeyboardButton("Subjects List", callback_data="list_subjects")],
                [InlineKeyboardButton("Search PDF", callback_data="search_file")],
                [InlineKeyboardButton("Total Subjects", callback_data="total_subjects")],
                [InlineKeyboardButton("Total PDFs in Subject", callback_data="total_pdfs")]]
    reply_markup = InlineKeyboardMarkup(services)
    
    USER_SESSION[user.id] = datetime.now()
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)

def check_session(user_id):
    if user_id in USER_SESSION:
        last_interaction = USER_SESSION[user_id]
        if datetime.now() - last_interaction > timedelta(minutes=5):
            del USER_SESSION[user_id]
            return False
    return True

def save_data():
    with open(DATA_FILE, "w") as f:
        json.dump(file_metadata, f)
    with open(USER_PREFS_FILE, "w") as f:
        json.dump(user_preferences, f)

async def handle_document(update: Update, context: CallbackContext):
    document = update.message.document
    user = update.message.from_user

    if user.id not in file_metadata:
        file_metadata[user.id] = {"uploaded": 0}
    
    file_metadata[user.id][document.file_name.lower()] = {
        "file_id": document.file_id,
        "uploader": user.first_name,
        "message_id": update.message.message_id
    }
    file_metadata[user.id]["uploaded"] += 1
    save_data()
    
    await update.message.reply_text(f"Thanks {user.first_name} for uploading {document.file_name}!")

async def search_file(update: Update, context: CallbackContext):
    query = " ".join(context.args).lower()
    results = [name for user_files in file_metadata.values() for name in user_files if query in name]
    
    if results:
        keyboard = [[InlineKeyboardButton(name, callback_data=name)] for name in results]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text("Select a file:", reply_markup=reply_markup)
    else:
        await update.message.reply_text("Sorry, no such file found.")

async def list_subjects(update: Update, context: CallbackContext):
    subjects = [name for user_files in file_metadata.values() for name in user_files if name != "uploaded"]
    if subjects:
        subjects_list = "\n".join(subjects)
        await update.message.reply_text(f"Available subjects:\n{subjects_list}")
    else:
        await update.message.reply_text("No subjects available yet.")

async def data_analysis(update: Update, context: CallbackContext):
    user = update.message.from_user
    if user.id != ADMIN_ID:
        await update.message.reply_text("You are not authorized to use this command.")
        return
    
    total_pdfs = sum(user_files.get("uploaded", 0) for user_files in file_metadata.values())
    user_stats = "\n".join([f"{user_id}: {user_files.get('uploaded', 0)} PDFs" for user_id, user_files in file_metadata.items()])
    
    analysis_message = f"Total PDFs uploaded: {total_pdfs}\n\nUploads per user:\n{user_stats}"
    await update.message.reply_text(analysis_message)

async def button(update: Update, context: CallbackContext):
    query = update.callback_query
    await query.answer()
    filename = query.data
    
    if filename == "list_subjects":
        await list_subjects(update, context)
    elif filename == "search_file":
        await update.callback_query.message.reply_text("Use /search <filename> to find a file.")
    else:
        for user_files in file_metadata.values():
            if filename in user_files:
                file_id = user_files[filename]["file_id"]
                uploader = user_files[filename]["uploader"]
                await query.message.reply_text(f"Here is the file '{filename}' uploaded by {uploader}:")
                await query.message.reply_document(file_id)
                return

async def handle_group_messages(update: Update, context: CallbackContext):
    user = update.message.from_user
    text = update.message.text.lower()
    
    if not check_session(user.id):
        await start(update, context)
        return
    
    USER_SESSION[user.id] = datetime.now()
    
    if text == "hi":
        await start(update, context)
    elif text in file_metadata:
        file_info = file_metadata[text]
        await update.message.reply_document(file_info["file_id"], caption=f"Here is the file for {text}.")
    else:
        await update.message.reply_text("I can help with subject PDFs! Say 'hi' to get started.")

def main():
    nest_asyncio.apply()
    asyncio.get_event_loop().run_until_complete(run_bot())

async def run_bot():
    app = Application.builder().token(TOKEN).build()
    
    scheduler = AsyncIOScheduler(timezone=pytz.utc)
    scheduler.start()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("data_analysis", data_analysis))
    app.add_handler(MessageHandler(filters.Document.ALL, handle_document))
    app.add_handler(CommandHandler("search", search_file))
    app.add_handler(CommandHandler("list", list_subjects))
    app.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, start))
    app.add_handler(CallbackQueryHandler(button))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_group_messages))

    print("Bot is running...")
    await app.run_polling()

if __name__ == "__main__":
    main()
