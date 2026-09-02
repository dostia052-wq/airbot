import os
import logging
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

BOT_TOKEN = os.getenv("BOT_TOKEN")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات ایردراپ با موفقیت روشن شد.")

def main():
    if not BOT_TOKEN:
        print("خطا: BOT_TOKEN تنظیم نشده است!")
        return

    application = ApplicationBuilder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    
    print("ربات در حال اجراست...")
    application.run_polling()

if __name__ == '__main__':
    main()
