import os
import logging
import asyncpg
from io import BytesIO
from datetime import date
import matplotlib.pyplot as plt
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
)

TOKEN = "8399118759:AAHPcVstB2N9l94Aorf-WGxbKHomv_EUepI"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"https://api.telegram.org/bot8399118759:AAHPcVstB2N9l94Aorf-WGxbKHomv_EUepI/setWebhook?url=https://darseman.onrender.com/8399118759:AAHPcVstB2N9l94Aorf-WGxbKHomv_EUepI{WEBHOOK_PATH}"
DB_URL = "postgresql://neondb_owner:npg_WtA2VhMHKcg6@ep-lively-queen-aely0rq7-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# ⚙️ لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)

# 📦 FastAPI app
app = FastAPI()

# 🎯 ساخت ربات تلگرام
application = Application.builder().token(TOKEN).updater(None).build()

# حالات کانورسیشن
CHOOSE_LANG, ENTER_NAME, MAIN, LOG_STUDY_SUBJECT, LOG_STUDY_TIME, LOG_TEST_SUBJECT, LOG_TEST_COUNT, VIEW_CHART = range(8)

db_pool = None

def get_message(lang, key):
    messages = {
        'en': {
            'choose_lang': "Choose language:",
            'enter_name': "Enter your name:",
            'welcome_back': "Welcome back, {name}!",
            'saved': "Your profile is saved!",
            'main_menu': "Main Menu",
            'enter_subject': "Enter the subject:",
            'enter_time': "Enter study time in minutes:",
            'invalid_time': "Invalid time. Please enter a number.",
            'logged': "Study logged successfully!",
            'enter_test_count': "Enter the number of tests:",
            'invalid_count': "Invalid count. Please enter a number.",
            'tests_logged': "Tests logged successfully!",
            'no_data': "No data available for the chart.",
            'study_chart_title': "Study Hours (Last 7 Days)",
            'test_chart_title': "Tests Taken (Last 7 Days)",
            'date_label': "Date",
            'hours_label': "Hours",
            'count_label': "Count",
        },
        'fa': {
            'choose_lang': "زبان را انتخاب کنید:",
            'enter_name': "نام خود را وارد کنید:",
            'welcome_back': "خوش آمدید دوباره، {name}!",
            'saved': "پروفایل شما ذخیره شد!",
            'main_menu': "منوی اصلی",
            'enter_subject': "درس را وارد کنید:",
            'enter_time': "زمان مطالعه را به دقیقه وارد کنید:",
            'invalid_time': "زمان نامعتبر. لطفا عدد وارد کنید.",
            'logged': "مطالعه ثبت شد!",
            'enter_test_count': "تعداد تست‌ها را وارد کنید:",
            'invalid_count': "تعداد نامعتبر. لطفا عدد وارد کنید.",
            'tests_logged': "تست‌ها ثبت شد!",
            'no_data': "داده‌ای برای نمودار موجود نیست.",
            'study_chart_title': "ساعات مطالعه (۷ روز اخیر)",
            'test_chart_title': "تست‌های زده‌شده (۷ روز اخیر)",
            'date_label': "تاریخ",
            'hours_label': "ساعات",
            'count_label': "تعداد",
        }
    }
    return messages.get(lang, messages['en']).get(key, "")

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("فارسی", callback_data='lang_fa'), InlineKeyboardButton("English", callback_data='lang_en')]
    ])

def main_menu_keyboard(lang):
    buttons = [
        [InlineKeyboardButton("ثبت مطالعه" if lang == 'fa' else "Log Study", callback_data='log_study')],
        [InlineKeyboardButton("نمودار مطالعه" if lang == 'fa' else "View Study Chart", callback_data='view_study')],
        [InlineKeyboardButton("ثبت تست" if lang == 'fa' else "Log Test", callback_data='log_test')],
        [InlineKeyboardButton("نمودار تست" if lang == 'fa' else "View Test Chart", callback_data='view_test')],
    ]
    return InlineKeyboardMarkup(buttons)

async def generate_chart(user_id, lang, is_study=True):
    plt.switch_backend('Agg')
    table = 'study_logs' if is_study else 'test_logs'
    field = 'minutes' if is_study else 'count'
    label = 'hours_label' if is_study else 'count_label'
    title_key = 'study_chart_title' if is_study else 'test_chart_title'
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT date, SUM({field}) as total FROM {table} WHERE user_id = $1 AND date > CURRENT_DATE - INTERVAL '7 days' GROUP BY date ORDER BY date",
            user_id
        )
    if not rows:
        return None, get_message(lang, 'no_data')
    
    dates = [row['date'] for row in rows]
    values = [row['total'] / 60 if is_study else row['total'] for row in rows]
    
    fig, ax = plt.subplots()
    ax.bar(dates, values)
    ax.set_xlabel(get_message(lang, 'date_label'))
    ax.set_ylabel(get_message(lang, label))
    ax.set_title(get_message(lang, title_key))
    plt.xticks(rotation=45)
    
    buf = BytesIO()
    plt.savefig(buf, format='png', bbox_inches='tight')
    buf.seek(0)
    plt.close(fig)
    return buf, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow('SELECT name, language FROM users WHERE id = $1', user_id)
    if row:
        context.user_data['lang'] = row['language']
        context.user_data['name'] = row['name']
        lang = context.user_data['lang']
        await update.message.reply_text(get_message(lang, 'welcome_back').format(name=row['name']), reply_markup=main_menu_keyboard(lang))
        return MAIN
    else:
        await update.message.reply_text(get_message('en', 'choose_lang'), reply_markup=lang_keyboard())  # Default to en for choose
        return CHOOSE_LANG

async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = query.data.split('_')[1]
    context.user_data['lang'] = lang
    await query.edit_message_text(text=get_message(lang, 'enter_name'))
    return ENTER_NAME

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data['lang']
    name = update.message.text.strip()
    if not name:
        await update.message.reply_text(get_message(lang, 'enter_name'))
        return ENTER_NAME
    context.user_data['name'] = name
    user_id = update.effective_user.id
    async with db_pool.acquire() as conn:
        await conn.execute('INSERT INTO users (id, name, language) VALUES ($1, $2, $3)', user_id, name, lang)
    await update.message.reply_text(get_message(lang, 'saved'), reply_markup=main_menu_keyboard(lang))
    return MAIN

async def main_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    lang = context.user_data['lang']
    data = query.data
    if data == 'log_study':
        await query.edit_message_text(get_message(lang, 'enter_subject'))
        return LOG_STUDY_SUBJECT
    elif data == 'log_test':
        await query.edit_message_text(get_message(lang, 'enter_subject'))
        return LOG_TEST_SUBJECT
    elif data == 'view_study' or data == 'view_test':
        is_study = data == 'view_study'
        buf, err = await generate_chart(update.effective_user.id, lang, is_study=is_study)
        if err:
            await query.edit_message_text(err, reply_markup=main_menu_keyboard(lang))
        else:
            await query.message.reply_photo(photo=buf)
            await query.message.reply_text(get_message(lang, 'main_menu'), reply_markup=main_menu_keyboard(lang))
        return MAIN
    return MAIN

async def log_study_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data['lang']
    subject = update.message.text.strip()
    if not subject:
        await update.message.reply_text(get_message(lang, 'enter_subject'))
        return LOG_STUDY_SUBJECT
    context.user_data['temp_subject'] = subject
    await update.message.reply_text(get_message(lang, 'enter_time'))
    return LOG_STUDY_TIME

async def log_study_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data['lang']
    try:
        minutes = int(update.message.text.strip())
        if minutes <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(get_message(lang, 'invalid_time'))
        return LOG_STUDY_TIME
    user_id = update.effective_user.id
    subject = context.user_data.pop('temp_subject', None)
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO study_logs (user_id, date, subject, minutes) VALUES ($1, CURRENT_DATE, $2, $3)',
            user_id, subject, minutes
        )
    await update.message.reply_text(get_message(lang, 'logged'), reply_markup=main_menu_keyboard(lang))
    return MAIN

async def log_test_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data['lang']
    subject = update.message.text.strip()
    if not subject:
        await update.message.reply_text(get_message(lang, 'enter_subject'))
        return LOG_TEST_SUBJECT
    context.user_data['temp_subject'] = subject
    await update.message.reply_text(get_message(lang, 'enter_test_count'))
    return LOG_TEST_COUNT

async def log_test_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    lang = context.user_data['lang']
    try:
        count = int(update.message.text.strip())
        if count <= 0:
            raise ValueError
    except ValueError:
        await update.message.reply_text(get_message(lang, 'invalid_count'))
        return LOG_TEST_COUNT
    user_id = update.effective_user.id
    subject = context.user_data.pop('temp_subject', None)
    async with db_pool.acquire() as conn:
        await conn.execute(
            'INSERT INTO test_logs (user_id, date, subject, count) VALUES ($1, CURRENT_DATE, $2, $3)',
            user_id, subject, count
        )
    await update.message.reply_text(get_message(lang, 'tests_logged'), reply_markup=main_menu_keyboard(lang))
    return MAIN

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        CHOOSE_LANG: [CallbackQueryHandler(choose_lang, pattern='^lang_')],
        ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
        MAIN: [CallbackQueryHandler(main_button)],
        LOG_STUDY_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_study_subject)],
        LOG_STUDY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_study_time)],
        LOG_TEST_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_test_subject)],
        LOG_TEST_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_test_count)],
    },
    fallbacks=[],
)

application.add_handler(conv_handler)

# 🔁 وب‌هوک تلگرام
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    data = await request.json()
    update = Update.de_json(data, application.bot)
    await application.process_update(update)
    return {"ok": True}

# 🔥 زمان بالا آمدن سرور
@app.on_event("startup")
async def on_startup():
    global db_pool
    db_pool = await asyncpg.create_pool(dsn=DB_URL)
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS users (
                id BIGINT PRIMARY KEY,
                name TEXT NOT NULL,
                language TEXT NOT NULL
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS study_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                date DATE NOT NULL,
                subject TEXT NOT NULL,
                minutes INTEGER NOT NULL
            )
        ''')
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS test_logs (
                id SERIAL PRIMARY KEY,
                user_id BIGINT REFERENCES users(id),
                date DATE NOT NULL,
                subject TEXT NOT NULL,
                count INTEGER NOT NULL
            )
        ''')
    await application.bot.set_webhook(url=WEBHOOK_URL)
    await application.initialize()
    await application.start()
    print("✅ Webhook set:", WEBHOOK_URL)

# 🛑 هنگام خاموشی
@app.on_event("shutdown")
async def on_shutdown():
    await application.stop()
    await application.shutdown()
    await db_pool.close()
