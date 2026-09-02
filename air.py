import os
from telegram import Update
from telegram.ext import ApplicationBuilder, ContextTypes, CommandHandler

BOT_TOKEN = os.getenv("BOT_TOKEN")
OWNER_ID = os.getenv("OWNER_ID")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("سلام! ربات ایردراپ با موفقیت روشن شد و روی رندر کار می‌کند.")

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
