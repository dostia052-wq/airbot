import logging
import sqlite3
from datetime import datetime, time
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.request import HTTPXRequest
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, 
    MessageHandler, ConversationHandler, ContextTypes, filters
)

logging.basicConfig(level=logging.INFO)

# تنظیمات اصلی مالک و توکن ربات
OWNER_ID = 8681480559
BOT_TOKEN = "8313645931:AAGj8EtyoLN25ZWXq6ZG_6GEsfeHZ2KqFLI"

# --- دیتابیس ---
def init_db():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS groups (chat_id INTEGER PRIMARY KEY, title TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS admins (user_id INTEGER PRIMARY KEY)")
    cursor.execute("CREATE TABLE IF NOT EXISTS messages (id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, text TEXT, file_id TEXT, media_type TEXT, caption TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)")
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS keywords (
            id INTEGER PRIMARY KEY AUTOINCREMENT, 
            keyword TEXT UNIQUE, 
            text TEXT, 
            file_id TEXT, 
            media_type TEXT, 
            caption TEXT
        )
    """)
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (OWNER_ID,))
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('auto_send', 'off')")
    conn.commit()
    conn.close()

def add_group(chat_id, title):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO groups (chat_id, title) VALUES (?, ?)", (chat_id, title))
    conn.commit()
    conn.close()

def remove_group(chat_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM groups WHERE chat_id = ?", (chat_id,))
    conn.commit()
    conn.close()

def get_groups():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT chat_id, title FROM groups")
    rows = cursor.fetchall()
    conn.close()
    return rows

def is_admin(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins WHERE user_id = ?", (user_id,))
    res = cursor.fetchone()
    conn.close()
    return res is not None

def get_admins():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM admins")
    rows = cursor.fetchall()
    conn.close()
    return [r[0] for r in rows]

def add_admin(user_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO admins (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def remove_admin(user_id):
    if user_id == OWNER_ID:
        return False
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM admins WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()
    return True

def save_msg(title, text, file_id, media_type, caption):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT INTO messages (title, text, file_id, media_type, caption) VALUES (?, ?, ?, ?, ?)", 
                   (title, text, file_id, media_type, caption))
    msg_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return msg_id

def update_msg(msg_id, title, text, file_id, media_type, caption):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("UPDATE messages SET title=?, text=?, file_id=?, media_type=?, caption=? WHERE id=?", 
                   (title, text, file_id, media_type, caption, msg_id))
    conn.commit()
    conn.close()

def get_all_msgs():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title FROM messages")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_msg_by_id(msg_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, title, text, file_id, media_type, caption FROM messages WHERE id=?", (msg_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_msg(msg_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM messages WHERE id=?", (msg_id,))
    conn.commit()
    conn.close()

def get_setting(key):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    res = cursor.fetchone()
    conn.close()
    return res[0] if res else "off"

def set_setting(key, value):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def add_keyword_full(keyword, text, file_id, media_type, caption):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("""
        INSERT OR REPLACE INTO keywords (keyword, text, file_id, media_type, caption) 
        VALUES (?, ?, ?, ?, ?)
    """, (keyword.lower().strip(), text, file_id, media_type, caption))
    conn.commit()
    conn.close()

def get_all_keywords():
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, keyword, media_type FROM keywords")
    rows = cursor.fetchall()
    conn.close()
    return rows

def get_keyword_by_id(kw_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, keyword, text, file_id, media_type, caption FROM keywords WHERE id=?", (kw_id,))
    row = cursor.fetchone()
    conn.close()
    return row

def delete_keyword(kw_id):
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("DELETE FROM keywords WHERE id=?", (kw_id,))
    conn.commit()
    conn.close()

init_db()

GET_ADD_ADMIN, GET_REM_ADMIN, GET_ADD_GROUP, GET_MSG_CONTENT, GET_EDIT_CONTENT, GET_INSTANT_CONTENT, GET_KEYWORD_TEXT, GET_KEYWORD_CONTENT = range(8)

def get_main_keyboard(user_id):
    auto_status = get_setting("auto_send")
    auto_btn_text = "🟢 ارسال خودکار: روشن" if auto_status == "on" else "🔴 ارسال خودکار: خاموش"
    
    keyboard = [
        [InlineKeyboardButton("⚡ ارسال فوری", callback_data="instant_send_start")],
        [InlineKeyboardButton(auto_btn_text, callback_data="toggle_auto_send")],
        [InlineKeyboardButton("🤖 پاسخ‌گویی خودکار", callback_data="auto_reply_menu")],
        [InlineKeyboardButton("✉️ مدیریت پیام‌ها", callback_data="msg_menu")],
        [InlineKeyboardButton("📁 مدیریت گروه‌ها", callback_data="group_menu")],
        [InlineKeyboardButton("⚙️ مدیریت ادمین‌ها", callback_data="admin_menu")],
        [InlineKeyboardButton("📞 تماس با پشتیبانی", url="https://t.me/Amiiiiiiiiiiiiiriiiii")]
    ]
    if user_id == OWNER_ID:
        keyboard.insert(4, [InlineKeyboardButton("👑 انتقال مالکیت در گروه", callback_data="transfer_list")])
        
    return InlineKeyboardMarkup(keyboard)

async def track_groups(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    if chat and chat.type in ["group", "supergroup"]:
        try:
            member = await context.bot.get_chat_member(chat.id, context.bot.id)
            if member.status in ["administrator", "creator"]:
                add_group(chat.id, chat.title)
        except Exception:
            pass

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_name = update.effective_user.first_name or "کاربر"

    if update.effective_chat.type != "private":
        return

    if not is_admin(user_id):
        user_keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 تماس با پشتیبانی", url="https://t.me/Amiiiiiiiiiiiiiriiiii")]
        ])
        welcome_text = (
            f"سلام {user_name} عزیز 👋\n\n"
            "به ربات خوش آمدید! 🌹\n"
            "برای ارتباط با مدیریت و ارسال پیام یا پشتیبانی، از دکمه زیر استفاده کنید:"
        )
        await update.message.reply_text(welcome_text, reply_markup=user_keyboard)
        return

    await update.message.reply_text(
        "👋 به پنل پیشرفته مدیریت ربات خوش آمدید.\nلطفاً بخش مورد نظر را انتخاب کنید:",
        reply_markup=get_main_keyboard(user_id)
    )

async def auto_send_job(context: ContextTypes.DEFAULT_TYPE):
    if get_setting("auto_send") != "on":
        return
    
    groups = get_groups()
    msgs = get_all_msgs()
    
    if not groups or not msgs:
        return

    msg_index = context.bot_data.get("rot_msg_index", 0) % len(msgs)
    group_index = context.bot_data.get("rot_group_index", 0) % len(groups)
    
    m_id = msgs[msg_index][0]
    target_chat, target_title = groups[group_index]
    
    context.bot_data["rot_msg_index"] = (msg_index + 1) % len(msgs)
    context.bot_data["rot_group_index"] = (group_index + 1) % len(groups)

    msg = get_msg_by_id(m_id)
    if not msg:
        return

    time_now = datetime.now().strftime("%H:%M:%S")

    try:
        m_type = msg[4]
        if m_type == "text":
            await context.bot.send_message(chat_id=target_chat, text=msg[2])
        elif m_type == "photo":
            await context.bot.send_photo(chat_id=target_chat, photo=msg[3], caption=msg[5])
        elif m_type == "video":
            await context.bot.send_video(chat_id=target_chat, video=msg[3], caption=msg[5])
        elif m_type == "voice":
            await context.bot.send_voice(chat_id=target_chat, voice=msg[3], caption=msg[5])
        elif m_type == "audio":
            await context.bot.send_audio(chat_id=target_chat, audio=msg[3], caption=msg[5])
        elif m_type == "document":
            await context.bot.send_document(chat_id=target_chat, document=msg[3], caption=msg[5])
        elif m_type == "animation":
            await context.bot.send_animation(chat_id=target_chat, animation=msg[3], caption=msg[5])
        elif m_type == "sticker":
            await context.bot.send_sticker(chat_id=target_chat, sticker=msg[3])
        
        report = (
            "🤖 **گزارش ارسال خودکار (موفق)**\n\n"
            f"📌 **نام گروه:** {target_title}\n"
            f"✉️ **عنوان پیام:** {msg[1]}\n"
            f"⏰ **زمان ارسال:** {time_now}"
        )
        await context.bot.send_message(chat_id=OWNER_ID, text=report, parse_mode="Markdown")

    except Exception as e:
        error_report = (
            "⚠️ **گزارش خطای ارسال خودکار**\n\n"
            f"📌 **نام گروه:** {target_title}\n"
            f"❌ **علت خطا:** `{e}`\n"
            f"⏰ **زمان:** {time_now}"
        )
        await context.bot.send_message(chat_id=OWNER_ID, text=error_report, parse_mode="Markdown")

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user_id = query.from_user.id
    if not is_admin(user_id):
        await query.answer("دسترسی غیرمجاز!", show_alert=True)
        return

    data = query.data

    if data == "main_menu":
        await query.message.edit_text("👋 به پنل اصلی خوش آمدید:", reply_markup=get_main_keyboard(user_id))

    elif data == "toggle_auto_send":
        current = get_setting("auto_send")
        time_now = datetime.now().strftime("%H:%M:%S")
        if current == "on":
            set_setting("auto_send", "off")
            await query.answer("ارسال خودکار خاموش شد.", show_alert=True)
            await context.bot.send_message(chat_id=OWNER_ID, text=f"🔴 **ارسال خودکار توسط ادمین خاموش شد.**\n⏰ زمان: {time_now}", parse_mode="Markdown")
        else:
            set_setting("auto_send", "on")
            await query.answer("ارسال خودکار روشن شد.", show_alert=True)
            await context.bot.send_message(chat_id=OWNER_ID, text=f"🟢 **ارسال خودکار توسط ادمین روشن شد.**\n⏰ زمان: {time_now}", parse_mode="Markdown")
        await query.message.edit_text("👋 به پنل اصلی خوش آمدید:", reply_markup=get_main_keyboard(user_id))

    elif data == "auto_reply_menu":
        keyboard = [
            [InlineKeyboardButton("➕ افزودن کلمه کلیدی جدید", callback_data="add_keyword_start")],
            [InlineKeyboardButton("📋 لیست و حذف کلمات کلیدی", callback_data="list_keywords")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
        ]
        await query.message.edit_text("🤖 **منوی پاسخ‌گویی خودکار:**\nکلمات کلیدی و پاسخ‌های رسانه‌ای ربات را مدیریت کنید:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "add_keyword_start":
        await query.message.reply_text("لطفاً **کلمه کلیدی** مورد نظر خود را بفرستید:")
        return GET_KEYWORD_TEXT

    elif data == "list_keywords":
        keywords = get_all_keywords()
        if not keywords:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="auto_reply_menu")]]
            await query.message.edit_text("هیچ کلمه کلیدی ثبت نشده است!", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        keyboard = []
        for kw_id, kw, m_type in keywords:
            icon = "💬" if m_type == "text" else "📁"
            keyboard.append([
                InlineKeyboardButton(f"{icon} {kw} ({m_type})", callback_data=f"view_kw_{kw_id}"),
                InlineKeyboardButton("❌ حذف", callback_data=f"del_kw_{kw_id}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="auto_reply_menu")])
        await query.message.edit_text("لیست کلمات کلیدی ذخیره‌شده:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("view_kw_"):
        kw_id = int(data.split("_")[2])
        kw_data = get_keyword_by_id(kw_id)
        if not kw_data:
            await query.answer("یافت نشد!", show_alert=True)
            return
        text_info = f"🔑 **کلمه کلیدی:** `{kw_data[1]}`\n📦 **نوع پاسخ:** `{kw_data[4]}`"
        keyboard = [
            [InlineKeyboardButton("❌ حذف کلمه کلیدی", callback_data=f"del_kw_{kw_id}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_keywords")]
        ]
        await query.message.edit_text(text_info, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_kw_"):
        kw_id = int(data.split("_")[2])
        delete_keyword(kw_id)
        await query.answer("کلمه کلیدی با موفقیت حذف شد!", show_alert=True)
        
        keywords = get_all_keywords()
        keyboard = []
        for kw_id, kw, m_type in keywords:
            icon = "💬" if m_type == "text" else "📁"
            keyboard.append([
                InlineKeyboardButton(f"{icon} {kw} ({m_type})", callback_data=f"view_kw_{kw_id}"),
                InlineKeyboardButton("❌ حذف", callback_data=f"del_kw_{kw_id}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="auto_reply_menu")])
        await query.message.edit_text("لیست کلمات کلیدی ذخیره‌شده:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "admin_menu":
        keyboard = [
            [InlineKeyboardButton("➕ افزودن ادمین", callback_data="add_admin_start")],
            [InlineKeyboardButton("➖ حذف ادمین", callback_data="rem_admin_start")],
            [InlineKeyboardButton("📋 لیست ادمین‌ها", callback_data="list_admins")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
        ]
        await query.message.edit_text("منوی مدیریت ادمین‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "list_admins":
        admins = get_admins()
        text = "📋 **لیست ادمین‌های ربات:**\n\n"
        if user_id == OWNER_ID:
            for idx, adm in enumerate(admins, 1):
                text += f"{idx}. `{adm}` {'(مالک اصلی)' if adm == OWNER_ID else ''}\n"
        else:
            filtered_admins = [adm for adm in admins if adm != OWNER_ID]
            for idx, adm in enumerate(filtered_admins, 1):
                text += f"{idx}. کاربر ادمین\n"
                
        keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="admin_menu")]]
        await query.message.edit_text(text, parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "group_menu":
        keyboard = [
            [InlineKeyboardButton("➕ افزودن گروه (لینک/آیدی)", callback_data="add_group_start")],
            [InlineKeyboardButton("📋 لیست و حذف گروه‌ها", callback_data="list_groups")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
        ]
        await query.message.edit_text("منوی مدیریت گروه‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "list_groups":
        groups = get_groups()
        if not groups:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="group_menu")]]
            await query.message.edit_text("هیچ گروهی ثبت نشده است!", reply_markup=InlineKeyboardMarkup(keyboard))
            return

        keyboard = []
        for chat_id, title in groups:
            keyboard.append([
                InlineKeyboardButton(f"📌 {title}", callback_data="none"),
                InlineKeyboardButton("❌ حذف", callback_data=f"del_group_{chat_id}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="group_menu")])
        await query.message.edit_text("لیست گروه‌های ثبت‌شده:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_group_"):
        chat_id_to_del = int(data.split("_")[2])
        remove_group(chat_id_to_del)
        await query.answer("گروه با موفقیت حذف شد!", show_alert=True)
        
        groups = get_groups()
        keyboard = []
        for chat_id, title in groups:
            keyboard.append([
                InlineKeyboardButton(f"📌 {title}", callback_data="none"),
                InlineKeyboardButton("❌ حذف", callback_data=f"del_group_{chat_id}")
            ])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="group_menu")])
        await query.message.edit_text("لیست گروه‌های ثبت‌شده:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "msg_menu":
        keyboard = [
            [InlineKeyboardButton("➕ افزودن پیام جدید", callback_data="add_msg_start")],
            [InlineKeyboardButton("📋 لیست پیام‌ها / ارسال و ویرایش", callback_data="list_msgs")],
            [InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]
        ]
        await query.message.edit_text("منوی مدیریت پیام‌ها:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data == "list_msgs":
        msgs = get_all_msgs()
        if not msgs:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="msg_menu")]]
            await query.message.edit_text("هیچ پیامی ذخیره نشده است!", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        
        keyboard = []
        for m_id, m_title in msgs:
            keyboard.append([InlineKeyboardButton(f"✉️ {m_title}", callback_data=f"view_msg_{m_id}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="msg_menu")])
        await query.message.edit_text("پیام مورد نظر خود را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("view_msg_"):
        m_id = int(data.split("_")[2])
        msg = get_msg_by_id(m_id)
        if not msg:
            await query.answer("پیام یافت نشد!", show_alert=True)
            return

        keyboard = [
            [InlineKeyboardButton("🚀 ارسال به گروه", callback_data=f"send_msg_groups_{m_id}")],
            [InlineKeyboardButton("✏️ ویرایش پیام", callback_data=f"edit_msg_start_{m_id}")],
            [InlineKeyboardButton("❌ حذف پیام", callback_data=f"del_msg_{m_id}")],
            [InlineKeyboardButton("🔙 بازگشت به لیست", callback_data="list_msgs")]
        ]
        await query.message.edit_text(f"📌 **مدیریت پیام:**\n`{msg[1]}`\n\nعملیات مورد نظر را انتخاب کنید:", parse_mode="Markdown", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("del_msg_"):
        m_id = int(data.split("_")[2])
        delete_msg(m_id)
        await query.answer("پیام با موفقیت حذف شد!", show_alert=True)
        
        msgs = get_all_msgs()
        keyboard = []
        for m_id, m_title in msgs:
            keyboard.append([InlineKeyboardButton(f"✉️ {m_title}", callback_data=f"view_msg_{m_id}")])
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="msg_menu")])
        await query.message.edit_text("لیست پیام‌های ذخیره‌شده:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("send_msg_groups_"):
        m_id = int(data.split("_")[3])
        groups = get_groups()
        if not groups:
            await query.message.reply_text("هیچ گروهی برای ارسال پیام ثبت نشده است!")
            return
        
        keyboard = [[InlineKeyboardButton(f"📢 {title}", callback_data=f"do_send_{m_id}_{chat_id}")] for chat_id, title in groups]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data=f"view_msg_{m_id}")])
        await query.message.edit_text("گروه مقصد جهت ارسال پیام را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("do_send_"):
        parts = data.split("_")
        m_id = int(parts[2])
        target_chat = int(parts[3])
        msg = get_msg_by_id(m_id)
        
        if not msg:
            await query.answer("خطا: پیام یافت نشد!", show_alert=True)
            return

        user_name = query.from_user.full_name or query.from_user.username or str(user_id)
        time_now = datetime.now().strftime("%H:%M:%S")

        status_msg = await query.message.reply_text("⏳ در حال ارسال پیام...")

        try:
            m_type = msg[4]
            if m_type == "text":
                await context.bot.send_message(chat_id=target_chat, text=msg[2])
            elif m_type == "photo":
                await context.bot.send_photo(chat_id=target_chat, photo=msg[3], caption=msg[5])
            elif m_type == "video":
                await context.bot.send_video(chat_id=target_chat, video=msg[3], caption=msg[5])
            elif m_type == "voice":
                await context.bot.send_voice(chat_id=target_chat, voice=msg[3], caption=msg[5])
            elif m_type == "audio":
                await context.bot.send_audio(chat_id=target_chat, audio=msg[3], caption=msg[5])
            elif m_type == "document":
                await context.bot.send_document(chat_id=target_chat, document=msg[3], caption=msg[5])
            elif m_type == "animation":
                await context.bot.send_animation(chat_id=target_chat, animation=msg[3], caption=msg[5])
            elif m_type == "sticker":
                await context.bot.send_sticker(chat_id=target_chat, sticker=msg[3])
            
            report = (
                "✅ **ارسال دستی موفقیت‌آمیز بود!**\n\n"
                f"👤 **اقدام‌کننده:** {user_name}\n"
                f"✉️ **عنوان پیام:** {msg[1]}\n"
                f"⏰ **زمان ارسال:** {time_now}"
            )
            await status_msg.edit_text(report, parse_mode="Markdown")
            if user_id != OWNER_ID:
                await context.bot.send_message(chat_id=OWNER_ID, text=f"📋 **گزارش ارسال دستی:**\nتوسط ادمین `{user_name}` پیام ارسال شد.\n⏰ {time_now}", parse_mode="Markdown")

        except Exception as e:
            report = (
                "❌ **خطا در ارسال پیام!**\n\n"
                f"👤 **اقدام کننده:** {user_name}\n"
                f"⚠️ **علت خطا:** `{e}`\n"
                f"⏰ **زمان:** {time_now}"
            )
            await status_msg.edit_text(report, parse_mode="Markdown")

    elif data == "transfer_list":
        if user_id != OWNER_ID:
            await query.answer("دسترسی غیرمجاز!", show_alert=True)
            return
        groups = get_groups()
        if not groups:
            keyboard = [[InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")]]
            await query.message.edit_text("هیچ گروهی ثبت نشده است!", reply_markup=InlineKeyboardMarkup(keyboard))
            return
        keyboard = [[InlineKeyboardButton(f"👑 {title}", callback_data=f"transfer_to_{chat_id}")] for chat_id, title in groups]
        keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
        await query.message.edit_text("گروهی که می‌خواهید در آن مالکان ارتقا یابید را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))

    elif data.startswith("transfer_to_"):
        if user_id != OWNER_ID:
            await query.answer("دسترسی غیرمجاز!", show_alert=True)
            return
        target_chat = int(data.split("_")[2])
        try:
            await context.bot.promote_chat_member(
                chat_id=target_chat, user_id=user_id, can_manage_chat=True,
                can_delete_messages=True, can_manage_video_chats=True,
                can_restrict_members=True, can_promote_members=True,
                can_change_info=True, can_invite_users=True, can_pin_messages=True
            )
            await query.message.reply_text("دسترسی‌های کامل مدیریت به شما اعطا شد!")
        except Exception as e:
            await query.message.reply_text(f"خطا در اعطای دسترسی: {e}")

    elif data == "add_admin_start":
        if user_id != OWNER_ID:
            await query.message.reply_text("فقط مالک اصلی می‌تواند ادمین جدید اضافه کند!")
            return
        await query.message.reply_text("آیدی عددی کاربر مورد نظر را بفرستید:")
        return GET_ADD_ADMIN

    elif data == "rem_admin_start":
        if user_id != OWNER_ID:
            await query.message.reply_text("فقط مالک اصلی می‌تواند ادمین را حذف کند!")
            return
        await query.message.reply_text("آیدی عددی ادمینی که می‌خواهید حذف شود را بفرستید:")
        return GET_REM_ADMIN

    elif data == "add_group_start":
        await query.message.reply_text("لینک دعوت گروه یا آیدی عددی را بفرستید:")
        return GET_ADD_GROUP

    elif data == "add_msg_start":
        await query.message.reply_text("متن یا رسانه پیام خود را بفرستید:")
        return GET_MSG_CONTENT

    elif data == "instant_send_start":
        await query.message.reply_text("⚡ **ارسال فوری:**\nلطفاً پیام خود را بفرستید تا بلافاصله لیست گروه‌ها نمایش داده شود:")
        return GET_INSTANT_CONTENT

    elif data.startswith("edit_msg_start_"):
        context.user_data["edit_msg_id"] = int(data.split("_")[3])
        await query.message.reply_text("محتوای جدید پیام را بفرستید:")
        return GET_EDIT_CONTENT

async def process_add_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        new_admin = int(update.message.text.strip())
        add_admin(new_admin)
        await update.message.reply_text(f"کاربر {new_admin} ادمین شد.")
        await context.bot.send_message(chat_id=OWNER_ID, text=f"👤 **ادمین جدید:** `{new_admin}`", parse_mode="Markdown")
    except Exception:
        await update.message.reply_text("آیدی نامعتبر!")
    return ConversationHandler.END

async def process_rem_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        rem_id = int(update.message.text.strip())
        if remove_admin(rem_id):
            await update.message.reply_text(f"کاربر {rem_id} حذف شد.")
            await context.bot.send_message(chat_id=OWNER_ID, text=f"👤 **حذف ادمین:** `{rem_id}`", parse_mode="Markdown")
        else:
            await update.message.reply_text("امکان حذف مالک اصلی نیست.")
    except Exception:
        await update.message.reply_text("آیدی نامعتبر!")
    return ConversationHandler.END

async def process_add_group(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text.strip()
    try:
        if "t.me/" in text or "telegram.me/" in text:
            chat = await context.bot.join_chat(text)
            add_group(chat.id, chat.title)
            await update.message.reply_text(f"گروه {chat.title} ثبت شد.")
            await context.bot.send_message(chat_id=OWNER_ID, text=f"📁 **گروه جدید:** {chat.title} (`{chat.id}`)", parse_mode="Markdown")
        else:
            chat_id = int(text)
            chat = await context.bot.get_chat(chat_id)
            add_group(chat.id, chat.title)
            await update.message.reply_text(f"گروه {chat.title} ثبت شد.")
            await context.bot.send_message(chat_id=OWNER_ID, text=f"📁 **گروه جدید:** {chat.title} (`{chat.id}`)", parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"خطا: {e}")
    return ConversationHandler.END

async def process_msg_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text, file_id, m_type, caption = None, None, "text", None
    
    if msg.text:
        text = msg.text
        title = text[:15] + "..." if len(text) > 15 else text
    elif msg.photo:
        file_id, m_type, caption = msg.photo[-1].file_id, "photo", msg.caption
        title = "🖼️ عکس"
    elif msg.video:
        file_id, m_type, caption = msg.video.file_id, "video", msg.caption
        title = "🎥 ویدیو"
    elif msg.voice:
        file_id, m_type, caption = msg.voice.file_id, "voice", msg.caption
        title = "🎙️ ویس"
    elif msg.audio:
        file_id, m_type, caption = msg.audio.file_id, "audio", msg.caption
        title = "🎵 آهنگ"
    elif msg.document:
        file_id, m_type, caption = msg.document.file_id, "document", msg.caption
        title = "📁 فایل"
    elif msg.animation:
        file_id, m_type, caption = msg.animation.file_id, "animation", msg.caption
        title = "🎞️ گیف"
    elif msg.sticker:
        file_id, m_type, caption = msg.sticker.file_id, "sticker", None
        title = "⭐ استیکر"

    save_msg(title, text, file_id, m_type, caption)
    await update.message.reply_text("پیام ذخیره شد.")
    return ConversationHandler.END

async def process_instant_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text, file_id, m_type, caption = None, None, "text", None
    
    if msg.text:
        text = msg.text
        title = text[:15] + "..." if len(text) > 15 else text
    elif msg.photo:
        file_id, m_type, caption = msg.photo[-1].file_id, "photo", msg.caption
        title = "🖼️ عکس"
    elif msg.video:
        file_id, m_type, caption = msg.video.file_id, "video", msg.caption
        title = "🎥 ویدیو"
    elif msg.voice:
        file_id, m_type, caption = msg.voice.file_id, "voice", msg.caption
        title = "🎙️ ویس"
    elif msg.audio:
        file_id, m_type, caption = msg.audio.file_id, "audio", msg.caption
        title = "🎵 آهنگ"
    elif msg.document:
        file_id, m_type, caption = msg.document.file_id, "document", msg.caption
        title = "📁 فایل"
    elif msg.animation:
        file_id, m_type, caption = msg.animation.file_id, "animation", msg.caption
        title = "🎞️ گیف"
    elif msg.sticker:
        file_id, m_type, caption = msg.sticker.file_id, "sticker", None
        title = "⭐ استیکر"

    m_id = save_msg(title, text, file_id, m_type, caption)
    groups = get_groups()
    if not groups:
        await update.message.reply_text("پیام ذخیره شد، اما گروهی ثبت نشده است!")
        return ConversationHandler.END

    keyboard = [[InlineKeyboardButton(f"📢 {title_g}", callback_data=f"do_send_{m_id}_{chat_id}")] for chat_id, title_g in groups]
    keyboard.append([InlineKeyboardButton("🔙 بازگشت", callback_data="main_menu")])
    await update.message.reply_text("گروه مقصد را انتخاب کنید:", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def process_edit_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    m_id = context.user_data.get("edit_msg_id")
    msg = update.message
    text, file_id, m_type, caption = None, None, "text", None
    
    if msg.text:
        text = msg.text
        title = text[:15] + "..." if len(text) > 15 else text
    elif msg.photo:
        file_id, m_type, caption = msg.photo[-1].file_id, "photo", msg.caption
        title = "🖼️ عکس"
    elif msg.video:
        file_id, m_type, caption = msg.video.file_id, "video", msg.caption
        title = "🎥 ویدیو"
    elif msg.voice:
        file_id, m_type, caption = msg.voice.file_id, "voice", msg.caption
        title = "🎙️ ویس"
    elif msg.audio:
        file_id, m_type, caption = msg.audio.file_id, "audio", msg.caption
        title = "🎵 آهنگ"
    elif msg.document:
        file_id, m_type, caption = msg.document.file_id, "document", msg.caption
        title = "📁 فایل"
    elif msg.animation:
        file_id, m_type, caption = msg.animation.file_id, "animation", msg.caption
        title = "🎞️ گیف"
    elif msg.sticker:
        file_id, m_type, caption = msg.sticker.file_id, "sticker", None
        title = "⭐ استیکر"

    update_msg(m_id, title, text, file_id, m_type, caption)
    await update.message.reply_text("پیام ویرایش شد.")
    return ConversationHandler.END

async def process_keyword_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    if not text:
        await update.message.reply_text("لطفاً یک متن معتبر برای کلمه کلیدی بفرستید:")
        return GET_KEYWORD_TEXT
    
    context.user_data["temp_keyword"] = text.strip()
    await update.message.reply_text(
        f"کلمه کلیدی: `{text}` ثبت شد.\n\n"
        "اکنون **متن یا رسانه پاسخ** (عکس، ویدیو، گیف، ویس، آهنگ، استیکر یا متن) را بفرستید:", 
        parse_mode="Markdown"
    )
    return GET_KEYWORD_CONTENT

async def process_keyword_content(update: Update, context: ContextTypes.DEFAULT_TYPE):
    msg = update.message
    text, file_id, m_type, caption = None, None, "text", None
    
    if msg.text:
        text = msg.text
    elif msg.photo:
        file_id, m_type, caption = msg.photo[-1].file_id, "photo", msg.caption
    elif msg.video:
        file_id, m_type, caption = msg.video.file_id, "video", msg.caption
    elif msg.voice:
        file_id, m_type, caption = msg.voice.file_id, "voice", msg.caption
    elif msg.audio:
        file_id, m_type, caption = msg.audio.file_id, "audio", msg.caption
    elif msg.document:
        file_id, m_type, caption = msg.document.file_id, "document", msg.caption
    elif msg.animation:
        file_id, m_type, caption = msg.animation.file_id, "animation", msg.caption
    elif msg.sticker:
        file_id, m_type, caption = msg.sticker.file_id, "sticker", None
    else:
        await update.message.reply_text("فرمت پشتیبانی نمی‌شود. لطفاً متن یا رسانه بفرستید:")
        return GET_KEYWORD_CONTENT

    keyword = context.user_data.get("temp_keyword")
    add_keyword_full(keyword, text, file_id, m_type, caption)
    
    await update.message.reply_text("✅ کلمه کلیدی و پاسخ رسانه‌ای آن با موفقیت ذخیره شد!")
    return ConversationHandler.END

async def auto_reply_checker(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat = update.effective_chat
    user = update.effective_user
    
    if not chat or chat.type not in ["group", "supergroup"]:
        return
    if not user or user.is_bot:
        return
    
    user_text = update.message.text or update.message.caption
    if not user_text:
        return
    
    conn = sqlite3.connect("bot_data.db")
    cursor = conn.cursor()
    cursor.execute("SELECT id, keyword, text, file_id, media_type, caption FROM keywords")
    keywords = cursor.fetchall()
    conn.close()
    
    user_text_lower = user_text.lower()
    
    for kw_id, kw, text, file_id, m_type, caption in keywords:
        if kw in user_text_lower:
            try:
                if m_type == "text":
                    await update.message.reply_text(text)
                elif m_type == "photo":
                    await update.message.reply_photo(photo=file_id, caption=caption)
                elif m_type == "video":
                    await update.message.reply_video(video=file_id, caption=caption)
                elif m_type == "voice":
                    await update.message.reply_voice(voice=file_id, caption=caption)
                elif m_type == "audio":
                    await update.message.reply_audio(audio=file_id, caption=caption)
                elif m_type == "document":
                    await update.message.reply_document(document=file_id, caption=caption)
                elif m_type == "animation":
                    await update.message.reply_animation(animation=file_id, caption=caption)
                elif m_type == "sticker":
                    await update.message.reply_sticker(sticker=file_id)
            except Exception:
                pass
            break

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("لغو شد.")
    return ConversationHandler.END

def main():
    req = HTTPXRequest(connect_timeout=30.0, read_timeout=30.0)
    app = Application.builder().token(BOT_TOKEN).request(req).build()

    job_queue = app.job_queue
    job_queue.run_repeating(auto_send_job, interval=1800, first=10)

    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern="^(add_admin_start|rem_admin_start|add_group_start|add_msg_start|instant_send_start|edit_msg_start_|add_keyword_start)")
        ],
        states={
            GET_ADD_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_admin)],
            GET_REM_ADMIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_rem_admin)],
            GET_ADD_GROUP: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_add_group)],
            GET_MSG_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, process_msg_content)],
            GET_INSTANT_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, process_instant_content)],
            GET_EDIT_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, process_edit_content)],
            GET_KEYWORD_TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_keyword_text)],
            GET_KEYWORD_CONTENT: [MessageHandler(filters.ALL & ~filters.COMMAND, process_keyword_content)]
        },
        fallbacks=[CommandHandler("cancel", cancel)]
    )

    app.add_handler(CommandHandler(["start", "panel"], start))
    app.add_handler(conv_handler)
    app.add_handler(CallbackQueryHandler(button_handler))
    app.add_handler(MessageHandler(filters.ChatType.GROUPS, track_groups))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, auto_reply_checker))

    print("ربات روشن شد و آماده به کار است...")
    app.run_polling()

if __name__ == "__main__":
    main()
