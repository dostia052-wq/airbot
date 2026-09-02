import os
import logging
import asyncio
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
    
    # راه‌اندازی دستی حلقه رویداد برای سازگاری کامل با تمام نسخه‌های پایتون
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    application.run_polling()

if __name__ == '__main__':
    main()
