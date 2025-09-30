import os
import logging
import asyncpg
import json
from io import BytesIO
from datetime import date, datetime
import matplotlib.pyplot as plt
import matplotlib.font_manager as fm
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
)

# تنظیم توکن و URL وب‌هوک
TOKEN = "8399118759:AAHPcVstB2N9l94Aorf-WGxbKHomv_EUepI"
ADMIN_ID = 8399118759  # آیدی ادمین - تغییر بده
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"https://darseman.onrender.com{WEBHOOK_PATH}"
DB_URL = "postgresql://neondb_owner:npg_WtA2VhMHKcg6@ep-lively-queen-aely0rq7-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# ⚙️ لاگ‌گیری
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

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
            'choose_lang': "🌍 Choose language:",
            'enter_name': "👤 Enter your name:",
            'welcome_back': "🎉 Welcome back, {name}!",
            'saved': "✅ Your profile is saved!",
            'main_menu': "📱 Main Menu",
            'enter_subject': "📚 Enter the subject:",
            'enter_time': "⏰ Enter study time in minutes:",
            'invalid_time': "❌ Invalid time. Please enter a number.",
            'logged': "✅ Study logged successfully!",
            'enter_test_count': "📊 Enter the number of tests:",
            'invalid_count': "❌ Invalid count. Please enter a number.",
            'tests_logged': "✅ Tests logged successfully!",
            'no_data': "📭 No data available for the chart.",
            'study_chart_title': "📈 Study Hours (Last 7 Days)",
            'test_chart_title': "📊 Tests Taken (Last 7 Days)",
            'date_label': "📅 Date",
            'hours_label': "⏰ Hours",
            'count_label': "📊 Count",
            'admin_stats': "👑 Admin Statistics\n\n👥 Total Users: {users}\n📚 Total Study Hours: {study_hours:.1f}\n📊 Total Tests: {tests}\n🕒 Last Update: {timestamp}",
            'backup_success': "✅ Backup created successfully!",
            'clear_success': "🗑️ Database cleared successfully!",
            'admin_only': "⛔ This command is for admin only!",
            'new_user_alert': "🆕 New User Alert!\n\n👤 Name: {name}\n🆔 ID: {id}\n🌐 Language: {lang}\n📅 Date: {date}",
        },
        'fa': {
            'choose_lang': "🌍 زبان را انتخاب کنید:",
            'enter_name': "👤 نام خود را وارد کنید:",
            'welcome_back': "🎉 خوش آمدید دوباره، {name}!",
            'saved': "✅ پروفایل شما ذخیره شد!",
            'main_menu': "📱 منوی اصلی",
            'enter_subject': "📚 درس را وارد کنید:",
            'enter_time': "⏰ زمان مطالعه را به دقیقه وارد کنید:",
            'invalid_time': "❌ زمان نامعتبر. لطفا عدد وارد کنید.",
            'logged': "✅ مطالعه ثبت شد!",
            'enter_test_count': "📊 تعداد تست‌ها را وارد کنید:",
            'invalid_count': "❌ تعداد نامعتبر. لطفا عدد وارد کنید.",
            'tests_logged': "✅ تست‌ها ثبت شد!",
            'no_data': "📭 داده‌ای برای نمودار موجود نیست.",
            'study_chart_title': "📈 ساعات مطالعه (۷ روز اخیر)",
            'test_chart_title': "📊 تست‌های زده‌شده (۷ روز اخیر)",
            'date_label': "📅 تاریخ",
            'hours_label': "⏰ ساعات",
            'count_label': "📊 تعداد",
            'admin_stats': "👑 آمار ادمین\n\n👥 کل کاربران: {users}\n📚 کل ساعات مطالعه: {study_hours:.1f}\n📊 کل تست‌ها: {tests}\n🕒 آخرین بروزرسانی: {timestamp}",
            'backup_success': "✅ بک‌آپ با موفقیت ایجاد شد!",
            'clear_success': "🗑️ پایگاه داده با موفقیت پاک شد!",
            'admin_only': "⛔ این دستور فقط برای ادمین است!",
            'new_user_alert': "🆕 کاربر جدید!\n\n👤 نام: {name}\n🆔 آیدی: {id}\n🌐 زبان: {lang}\n📅 تاریخ: {date}",
        }
    }
    return messages.get(lang, messages['en']).get(key, "")

def setup_persian_font():
    """تنظیم فونت فارسی برای نمودارها"""
    try:
        # استفاده از فونت پیش‌فرض سیستم که از فارسی پشتیبانی می‌کند
        plt.rcParams['font.family'] = 'DejaVu Sans'
        plt.rcParams['axes.unicode_minus'] = False
    except:
        pass

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data='lang_fa'), 
         InlineKeyboardButton("🇺🇸 English", callback_data='lang_en')]
    ])

def main_menu_keyboard(lang):
    buttons = [
        [InlineKeyboardButton("📚 ثبت مطالعه" if lang == 'fa' else "📚 Log Study", callback_data='log_study')],
        [InlineKeyboardButton("📈 نمودار مطالعه" if lang == 'fa' else "📈 View Study Chart", callback_data='view_study')],
        [InlineKeyboardButton("📊 ثبت تست" if lang == 'fa' else "📊 Log Test", callback_data='log_test')],
        [InlineKeyboardButton("📉 نمودار تست" if lang == 'fa' else "📉 View Test Chart", callback_data='view_test')],
    ]
    return InlineKeyboardMarkup(buttons)

async def generate_chart(user_id, lang, is_study=True):
    try:
        setup_persian_font()
        plt.switch_backend('Agg')
        plt.style.use('seaborn-v0_8')
        
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
        
        # ایجاد رنگ‌های مختلف برای هر ستون
        colors = plt.cm.viridis(range(len(dates)))
        
        fig, ax = plt.subplots(figsize=(10, 6))
        bars = ax.bar(dates, values, color=colors, alpha=0.7, edgecolor='black', linewidth=1.2)
        
        # اضافه کردن اعداد روی ستون‌ها
        for bar, value in zip(bars, values):
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height + 0.01,
                   f'{value:.1f}' if is_study else f'{int(value)}',
                   ha='center', va='bottom', fontsize=10, fontweight='bold')
        
        ax.set_xlabel(get_message(lang, 'date_label'), fontsize=12, fontweight='bold')
        ax.set_ylabel(get_message(lang, label), fontsize=12, fontweight='bold')
        ax.set_title(get_message(lang, title_key), fontsize=14, fontweight='bold', pad=20)
        
        # تنظیمات ظاهری
        ax.grid(True, alpha=0.3)
        plt.xticks(rotation=45, ha='right')
        plt.tight_layout()
        
        buf = BytesIO()
        plt.savefig(buf, format='png', dpi=150, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)
        return buf, None
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return None, get_message(lang, 'no_data')

async def setup_menu_commands():
    """تنظیم منوی همبرگری"""
    commands = [
        BotCommand("start", "شروع ربات / Start bot"),
        BotCommand("stats", "آمار ربات (ادمین) / Statistics (Admin)"),
        BotCommand("backup", "پشتیبان‌گیری (ادمین) / Backup (Admin)"),
        BotCommand("clear_db", "پاکسازی دیتابیس (ادمین) / Clear DB (Admin)"),
    ]
    await application.bot.set_my_commands(commands)

async def notify_admin_new_user(user_id, name, lang):
    """اعلام کاربر جدید به ادمین"""
    try:
        message = get_message('fa', 'new_user_alert').format(
            name=name,
            id=user_id,
            lang=lang,
            date=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        await application.bot.send_message(ADMIN_ID, message)
    except Exception as e:
        logger.error(f"Error notifying admin: {e}")

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = update.effective_user.id
        logger.info(f"Start command received from user_id: {user_id}")
        
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow('SELECT name, language FROM users WHERE id = $1', user_id)
        
        if row:
            context.user_data['lang'] = row['language']
            context.user_data['name'] = row['name']
            lang = context.user_data['lang']
            await update.message.reply_text(
                get_message(lang, 'welcome_back').format(name=row['name']), 
                reply_markup=main_menu_keyboard(lang)
            )
            return MAIN
        else:
            await update.message.reply_text(get_message('en', 'choose_lang'), reply_markup=lang_keyboard())
            return CHOOSE_LANG
    except Exception as e:
        logger.error(f"Error in start: {e}")
        await update.message.reply_text("❌ An error occurred. Please try again.")
        return ConversationHandler.END

async def choose_lang(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        lang = query.data.split('_')[1]
        context.user_data['lang'] = lang
        await query.edit_message_text(text=get_message(lang, 'enter_name'))
        return ENTER_NAME
    except Exception as e:
        logger.error(f"Error in choose_lang: {e}")
        return ConversationHandler.END

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data['lang']
        name = update.message.text.strip()
        if not name:
            await update.message.reply_text(get_message(lang, 'enter_name'))
            return ENTER_NAME
        
        context.user_data['name'] = name
        user_id = update.effective_user.id
        
        async with db_pool.acquire() as conn:
            await conn.execute('INSERT INTO users (id, name, language) VALUES ($1, $2, $3)', user_id, name, lang)
        
        # اطلاع به ادمین
        await notify_admin_new_user(user_id, name, lang)
        
        await update.message.reply_text(get_message(lang, 'saved'), reply_markup=main_menu_keyboard(lang))
        return MAIN
    except Exception as e:
        logger.error(f"Error in enter_name: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
        return ConversationHandler.END

async def main_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
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
                await query.message.reply_photo(photo=buf, caption=get_message(lang, 'main_menu'), reply_markup=main_menu_keyboard(lang))
            return MAIN
        return MAIN
    except Exception as e:
        logger.error(f"Error in main_button: {e}")
        await query.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
        return MAIN

async def log_study_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data['lang']
        subject = update.message.text.strip()
        if not subject:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_STUDY_SUBJECT
        context.user_data['temp_subject'] = subject
        await update.message.reply_text(get_message(lang, 'enter_time'))
        return LOG_STUDY_TIME
    except Exception as e:
        logger.error(f"Error in log_study_subject: {e}")
        return ConversationHandler.END

async def log_study_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
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
    except Exception as e:
        logger.error(f"Error in log_study_time: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
        return MAIN

async def log_test_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data['lang']
        subject = update.message.text.strip()
        if not subject:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_TEST_SUBJECT
        context.user_data['temp_subject'] = subject
        await update.message.reply_text(get_message(lang, 'enter_test_count'))
        return LOG_TEST_COUNT
    except Exception as e:
        logger.error(f"Error in log_test_subject: {e}")
        return ConversationHandler.END

async def log_test_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
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
    except Exception as e:
        logger.error(f"Error in log_test_count: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
        return MAIN

# دستورات ادمین
async def admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش آمار برای ادمین"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(get_message('en', 'admin_only'))
        return
    
    try:
        async with db_pool.acquire() as conn:
            # تعداد کاربران
            users_count = await conn.fetchval('SELECT COUNT(*) FROM users')
            
            # مجموع ساعات مطالعه
            total_minutes = await conn.fetchval('SELECT SUM(minutes) FROM study_logs') or 0
            total_study_hours = total_minutes / 60
            
            # مجموع تست‌ها
            total_tests = await conn.fetchval('SELECT SUM(count) FROM test_logs') or 0
        
        message = get_message('fa', 'admin_stats').format(
            users=users_count,
            study_hours=total_study_hours,
            tests=total_tests,
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )
        
        await update.message.reply_text(message)
    except Exception as e:
        logger.error(f"Error in admin_stats: {e}")
        await update.message.reply_text("❌ Error getting statistics")

async def backup_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پشتیبان‌گیری از دیتابیس"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(get_message('en', 'admin_only'))
        return
    
    try:
        async with db_pool.acquire() as conn:
            # دریافت داده‌ها از جداول
            users = await conn.fetch('SELECT * FROM users')
            study_logs = await conn.fetch('SELECT * FROM study_logs')
            test_logs = await conn.fetch('SELECT * FROM test_logs')
            
            backup_data = {
                'timestamp': datetime.now().isoformat(),
                'users': [dict(user) for user in users],
                'study_logs': [dict(log) for log in study_logs],
                'test_logs': [dict(log) for log in test_logs]
            }
            
            # ایجاد فایل بک‌آپ
            backup_file = BytesIO()
            backup_file.write(json.dumps(backup_data, indent=2, ensure_ascii=False).encode('utf-8'))
            backup_file.seek(0)
            backup_file.name = f'backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            
            await update.message.reply_document(
                document=backup_file,
                caption=get_message('fa', 'backup_success')
            )
    except Exception as e:
        logger.error(f"Error in backup_database: {e}")
        await update.message.reply_text("❌ Error creating backup")

async def clear_database(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """پاکسازی دیتابیس"""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text(get_message('en', 'admin_only'))
        return
    
    try:
        async with db_pool.acquire() as conn:
            await conn.execute('DELETE FROM test_logs')
            await conn.execute('DELETE FROM study_logs')
            await conn.execute('DELETE FROM users')
        
        await update.message.reply_text(get_message('fa', 'clear_success'))
    except Exception as e:
        logger.error(f"Error in clear_database: {e}")
        await update.message.reply_text("❌ Error clearing database")

# تنظیم هندلرها
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
application.add_handler(CommandHandler("stats", admin_stats))
application.add_handler(CommandHandler("backup", backup_database))
application.add_handler(CommandHandler("clear_db", clear_database))

# 🔁 وب‌هوک تلگرام
@app.post(WEBHOOK_PATH)
async def telegram_webhook(request: Request):
    try:
        data = await request.json()
        logger.info(f"Received webhook data: {data}")
        update = Update.de_json(data, application.bot)
        if update:
            await application.process_update(update)
            logger.info("Update processed successfully")
        else:
            logger.error("Failed to parse update")
        return {"ok": True}
    except Exception as e:
        logger.error(f"Error in webhook: {e}")
        return {"ok": False}

# 🔥 زمان بالا آمدن سرور
@app.on_event("startup")
async def on_startup():
    global db_pool
    try:
        logger.info("Starting up application...")
        db_pool = await asyncpg.create_pool(dsn=DB_URL)
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    language TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS study_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id),
                    date DATE NOT NULL,
                    subject TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS test_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id),
                    date DATE NOT NULL,
                    subject TEXT NOT NULL,
                    count INTEGER NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
        logger.info("Database tables created successfully")
        
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
        
        await setup_menu_commands()
        logger.info("Menu commands set up successfully")
        
        await application.initialize()
        await application.start()
        logger.info("Application started successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        raise

# 🛑 هنگام خاموشی
@app.on_event("shutdown")
async def on_shutdown():
    try:
        logger.info("Shutting down application...")
        await application.stop()
        await application.shutdown()
        if db_pool:
            await db_pool.close()
        logger.info("Application shutdown successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
