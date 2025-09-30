import os
import logging
import asyncpg
from io import BytesIO, StringIO
from datetime import date
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from fastapi import FastAPI, Request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, BotCommand
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ConversationHandler, ContextTypes
)

# تنظیم توکن و URL وب‌هوک
TOKEN = "8399118759:AAHPcVstB2N9l94Aorf-WGxbKHomv_EUepI"
WEBHOOK_PATH = f"/webhook/{TOKEN}"
WEBHOOK_URL = f"https://darseman.onrender.com{WEBHOOK_PATH}"
DB_URL = "postgresql://neondb_owner:npg_WtA2VhMHKcg6@ep-lively-queen-aely0rq7-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"
ADMIN_ID = 5542927340  # ایدی ادمین

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
CHOOSE_LANG, ENTER_NAME, ENTER_GRADE, MAIN, LOG_STUDY_SUBJECT, LOG_STUDY_TIME, LOG_TEST_SUBJECT, LOG_TEST_COUNT, \
CHOOSE_SUBJECT, CHOOSE_CHAPTER, CHOOSE_TIME, CONFIRM_READ, ENTER_NOTE, VIEW_REPORT = range(14)

db_pool = None

# دیکشنری درس‌ها بر اساس پایه
subjects_by_grade = {
    '10': ['شیمی', 'ریاضی', 'فیزیک', 'زیست'],
    '11': ['شیمی', 'ریاضی', 'فیزیک', 'زیست', 'زمین‌شناسی'],
    '12': ['شیمی', 'ریاضی', 'فیزیک', 'زیست'],
    'en_10': ['Chemistry', 'Math', 'Physics', 'Biology'],
    'en_11': ['Chemistry', 'Math', 'Physics', 'Biology', 'Geology'],
    'en_12': ['Chemistry', 'Math', 'Physics', 'Biology']
}

# دیکشنری تعداد فصل‌ها
chapters_by_subject = {
    '10': {'شیمی': 3, 'ریاضی': 7, 'فیزیک': 4, 'زیست': 7},
    '11': {'شیمی': 3, 'ریاضی': 7, 'فیزیک': 3, 'زیست': 9, 'زمین‌شناسی': 7},
    '12': {'شیمی': 4, 'ریاضی': 7, 'فیزیک': 4, 'زیست': 8},
    'en_10': {'Chemistry': 3, 'Math': 7, 'Physics': 4, 'Biology': 7},
    'en_11': {'Chemistry': 3, 'Math': 7, 'Physics': 3, 'Biology': 9, 'Geology': 7},
    'en_12': {'Chemistry': 4, 'Math': 7, 'Physics': 4, 'Biology': 8}
}

def get_message(lang, key):
    messages = {
        'en': {
            'choose_lang': "🌍 Choose language:",
            'enter_name': "📝 Enter your name:",
            'choose_grade': "📚 What grade are you in? (10th, 11th, 12th)",
            'welcome_back': "👋 Welcome back to My Lesson, {name}! 📚",
            'saved': "✅ Your profile is saved! 🎉",
            'main_menu': "📋 Main Menu",
            'enter_subject': "📖 Enter the subject:",
            'enter_time': "⏱️ Enter study time in minutes:",
            'invalid_time': "❌ Invalid time. Please enter a number.",
            'logged': "✅ Study logged successfully! 📈",
            'enter_test_count': "🧪 Enter the number of tests:",
            'invalid_count': "❌ Invalid count. Please enter a number.",
            'tests_logged': "✅ Tests logged successfully! 📊",
            'no_data': "📉 No data available.",
            'study_chart_title': "📚 Study Hours (Last 7 Days)",
            'test_chart_title': "🧪 Tests Taken (Last 7 Days)",
            'date_label': "📅 Date",
            'hours_label': "⏰ Hours",
            'count_label': "🔢 Count",
            'my_lessons': "📖 My Lessons",
            'choose_subject': "📚 Choose a subject:",
            'choose_chapter': "📖 Choose a chapter for {subject}:",
            'choose_time': "⏱️ Choose study time:",
            'confirm_read': "✅ Read it?",
            'enter_note': "📝 Do you have a note? (e.g., read half) or type 'none' to skip:",
            'lesson_logged': "✅ Lesson study logged! 📈",
            'view_report': "📊 View Study Report",
            'report_title': "📊 Study Report",
            'subjects_to_study': "📚 Subjects to study:",
            'total_time': "⏰ Total study time: {total} minutes",
            'notes': "📝 Notes:",
            'error': "⚠️ An error occurred. Please try again later."
        },
        'fa': {
            'choose_lang': "🌍 زبان را انتخاب کنید:",
            'enter_name': "📝 نام خود را وارد کنید:",
            'choose_grade': "📚 چندم هستید؟ (دهم، یازدهم، دوازدهم)",
            'welcome_back': "👋 خوش آمدید دوباره به درس من، {name}! 📚",
            'saved': "✅ پروفایل شما ذخیره شد! 🎉",
            'main_menu': "📋 منوی اصلی",
            'enter_subject': "📖 درس را وارد کنید:",
            'enter_time': "⏱️ زمان مطالعه را به دقیقه وارد کنید:",
            'invalid_time': "❌ زمان نامعتبر. لطفاً عدد وارد کنید.",
            'logged': "✅ مطالعه ثبت شد! 📈",
            'enter_test_count': "🧪 تعداد تست‌ها را وارد کنید:",
            'invalid_count': "❌ تعداد نامعتبر. لطفاً عدد وارد کنید.",
            'tests_logged': "✅ تست‌ها ثبت شد! 📊",
            'no_data': "📉 داده‌ای موجود نیست.",
            'study_chart_title': "📚 ساعات مطالعه (۷ روز اخیر)",
            'test_chart_title': "🧪 تست‌های زده‌شده (۷ روز اخیر)",
            'date_label': "📅 تاریخ",
            'hours_label': "⏰ ساعات",
            'count_label': "🔢 تعداد",
            'my_lessons': "📖 درس‌های من",
            'choose_subject': "📚 درس را انتخاب کنید:",
            'choose_chapter': "📖 فصل را برای {subject} انتخاب کنید:",
            'choose_time': "⏱️ زمان مطالعه را انتخاب کنید:",
            'confirm_read': "✅ خوندم",
            'enter_note': "📝 یادداشتی دارید؟ (مثلاً نصفشو خوندم) یا بنویسید 'هیچ' برای رد کردن:",
            'lesson_logged': "✅ مطالعه درس ثبت شد! 📈",
            'view_report': "📊 گزارش مطالعه",
            'report_title': "📊 گزارش مطالعه",
            'subjects_to_study': "📚 درس‌هایی که باید بخوانید:",
            'total_time': "⏰ مجموع زمان مطالعه: {total} دقیقه",
            'notes': "📝 یادداشت‌ها:",
            'error': "⚠️ خطایی رخ داد. لطفاً دوباره تلاش کنید."
        }
    }
    return messages.get(lang, messages['en']).get(key, "")

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data='lang_fa'), InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')]
    ])

def grade_keyboard(lang):
    if lang == 'fa':
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("دهم", callback_data='grade_10'),
             InlineKeyboardButton("یازدهم", callback_data='grade_11'),
             InlineKeyboardButton("دوازدهم", callback_data='grade_12')]
        ])
    else:
        return InlineKeyboardMarkup([
            [InlineKeyboardButton("10th", callback_data='grade_10'),
             InlineKeyboardButton("11th", callback_data='grade_11'),
             InlineKeyboardButton("12th", callback_data='grade_12')]
        ])

def main_menu_keyboard(lang):
    keyboard = [
        [KeyboardButton(get_message(lang, 'my_lessons'))],
        [KeyboardButton("📚 ثبت مطالعه" if lang == 'fa' else "📚 Log Study")],
        [KeyboardButton("📈 نمودار مطالعه" if lang == 'fa' else "📈 View Study Chart")],
        [KeyboardButton("🧪 ثبت تست" if lang == 'fa' else "🧪 Log Test")],
        [KeyboardButton("📊 نمودار تست" if lang == 'fa' else "📊 View Test Chart")],
        [KeyboardButton(get_message(lang, 'view_report'))],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def subjects_keyboard(lang, grade):
    key = 'en_' + grade if lang == 'en' else grade
    subjects = subjects_by_grade.get(key, [])
    keyboard = [[KeyboardButton(sub)] for sub in subjects]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def chapters_keyboard(lang, grade, subject):
    key = 'en_' + grade if lang == 'en' else grade
    num_chapters = chapters_by_subject.get(key, {}).get(subject, 0)
    chapters = [f"Chapter {i}" if lang == 'en' else f"فصل {i}" for i in range(1, num_chapters + 1)]
    keyboard = [[KeyboardButton(chap)] for chap in chapters]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def time_keyboard(lang):
    times = ['10', '20', '30', '45', '60', '90', '120']
    keyboard = [[KeyboardButton(time + (" minutes" if lang == 'en' else " دقیقه"))] for time in times]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)

def confirm_keyboard(lang):
    return InlineKeyboardMarkup([
        [InlineKeyboardButton(get_message(lang, 'confirm_read'), callback_data='read_confirm')]
    ])

async def generate_chart(user_id, lang, is_study=True):
    try:
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
        
        fig, ax = plt.subplots(figsize=(10, 6))
        colors = plt.cm.viridis(range(len(dates)))
        ax.bar(dates, values, color=colors, width=0.4)
        ax.set_xlabel(get_message(lang, 'date_label'), fontsize=12)
        ax.set_ylabel(get_message(lang, label), fontsize=12)
        ax.set_title(get_message(lang, title_key), fontsize=14)
        ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d'))
        plt.xticks(rotation=45, ha='right', fontsize=10)
        plt.yticks(fontsize=10)
        ax.grid(True, linestyle='--', alpha=0.7)
        
        if lang == 'fa':
            plt.rcParams['text.usetex'] = False
            plt.rcParams['font.family'] = 'sans-serif'
            plt.rcParams['font.sans-serif'] = ['DejaVuSans']
            ax.set_title(get_message(lang, title_key)[::-1], fontsize=14)
            ax.set_xlabel(get_message(lang, 'date_label')[::-1], fontsize=12)
            ax.set_ylabel(get_message(lang, label)[::-1], fontsize=12)
        
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf, None
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return None, get_message(lang, 'no_data')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.effective_user.id
    logger.info(f"Start command received from user_id: {user_id}")
    
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow('SELECT name, language, grade FROM users WHERE id = $1', user_id)
        
        if row:
            context.user_data['lang'] = row['language']
            context.user_data['name'] = row['name']
            context.user_data['grade'] = row['grade']
            lang = context.user_data['lang']
            await update.message.reply_text(
                get_message(lang, 'welcome_back').format(name=row['name']),
                reply_markup=main_menu_keyboard(lang)
            )
            return MAIN
        else:
            await update.message.reply_text(
                get_message('en', 'choose_lang'),
                reply_markup=lang_keyboard()
            )
            return CHOOSE_LANG
            
    except asyncpg.exceptions.InterfaceError as e:
        logger.error(f"Database connection error in start: {e}")
        await update.message.reply_text(
            get_message('en', 'error'),
            reply_markup=lang_keyboard()
        )
        return CHOOSE_LANG
    except Exception as e:
        logger.error(f"Unexpected error in start: {e}")
        await update.message.reply_text(
            get_message('en', 'error'),
            reply_markup=lang_keyboard()
        )
        return CHOOSE_LANG

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
        await query.message.reply_text(get_message('en', 'error'))
        return ConversationHandler.END

async def enter_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        name = update.message.text.strip()
        if not name:
            await update.message.reply_text(get_message(lang, 'enter_name'))
            return ENTER_NAME
        context.user_data['name'] = name
        await update.message.reply_text(get_message(lang, 'choose_grade'), reply_markup=grade_keyboard(lang))
        return ENTER_GRADE
    except Exception as e:
        logger.error(f"Error in enter_name: {e}")
        await update.message.reply_text(get_message(lang, 'error'))
        return ConversationHandler.END

async def enter_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        lang = context.user_data.get('lang', 'en')
        if query:
            await query.answer()
            grade = query.data.split('_')[1]
            reply_method = query.edit_message_text
            user_id = query.from_user.id
        else:
            text = update.message.text.strip()
            if lang == 'fa':
                grade_map = {'دهم': '10', 'یازدهم': '11', 'دوازدهم': '12'}
            else:
                grade_map = {'10th': '10', '11th': '11', '12th': '12'}
            grade = grade_map.get(text)
            if not grade:
                await update.message.reply_text(get_message(lang, 'choose_grade'))
                return ENTER_GRADE
            reply_method = update.message.reply_text
            user_id = update.message.from_user.id
        
        context.user_data['grade'] = grade
        name = context.user_data['name']
        async with db_pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO users (id, name, language, grade) VALUES ($1, $2, $3, $4) ON CONFLICT (id) DO UPDATE SET name = $2, language = $3, grade = $4',
                user_id, name, lang, grade
            )
        await reply_method(get_message(lang, 'saved'), reply_markup=main_menu_keyboard(lang))
        
        # اطلاع‌رسانی به ادمین
        await context.bot.send_message(ADMIN_ID, f"👤 کاربر جدید: {name} (ID: {user_id}, پایه: {grade})")
        
        return MAIN
    except Exception as e:
        logger.error(f"Error in enter_grade: {e}")
        await (query.message.reply_text if query else update.message.reply_text)(get_message(lang, 'error'))
        return ConversationHandler.END

async def main_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        text = update.message.text
        if text == get_message(lang, 'my_lessons'):
            await update.message.reply_text(
                get_message(lang, 'choose_subject'),
                reply_markup=subjects_keyboard(lang, context.user_data.get('grade', '10'))
            )
            return CHOOSE_SUBJECT
        elif text == get_message(lang, 'view_report'):
            return await view_report(update, context)
        elif text in ["📚 ثبت مطالعه", "📚 Log Study"]:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_STUDY_SUBJECT
        elif text in ["📈 نمودار مطالعه", "📈 View Study Chart"]:
            buf, err = await generate_chart(update.effective_user.id, lang, is_study=True)
            if err:
                await update.message.reply_text(err, reply_markup=main_menu_keyboard(lang))
            else:
                await update.message.reply_photo(photo=buf)
                await update.message.reply_text(get_message(lang, 'main_menu'), reply_markup=main_menu_keyboard(lang))
            return MAIN
        elif text in ["🧪 ثبت تست", "🧪 Log Test"]:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_TEST_SUBJECT
        elif text in ["📊 نمودار تست", "📊 View Test Chart"]:
            buf, err = await generate_chart(update.effective_user.id, lang, is_study=False)
            if err:
                await update.message.reply_text(err, reply_markup=main_menu_keyboard(lang))
            else:
                await update.message.reply_photo(photo=buf)
                await update.message.reply_text(get_message(lang, 'main_menu'), reply_markup=main_menu_keyboard(lang))
            return MAIN
        return MAIN
    except Exception as e:
        logger.error(f"Error in main_message: {e}")
        await update.message.reply_text(get_message(lang, 'error'))
        return MAIN

async def choose_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        grade = context.user_data.get('grade', '10')
        key = 'en_' + grade if lang == 'en' else grade
        subject = update.message.text.strip()
        if subject not in subjects_by_grade.get(key, []):
            await update.message.reply_text(get_message(lang, 'choose_subject'))
            return CHOOSE_SUBJECT
        context.user_data['temp_subject'] = subject
        await update.message.reply_text(
            get_message(lang, 'choose_chapter').format(subject=subject),
            reply_markup=chapters_keyboard(lang, grade, subject)
        )
        return CHOOSE_CHAPTER
    except Exception as e:
        logger.error(f"Error in choose_subject: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return ConversationHandler.END

async def choose_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        chapter = update.message.text.strip()
        if not chapter.startswith("فصل ") and not chapter.startswith("Chapter "):
            await update.message.reply_text(
                get_message(lang, 'choose_chapter').format(subject=context.user_data.get('temp_subject', ''))
            )
            return CHOOSE_CHAPTER
        context.user_data['temp_chapter'] = chapter
        await update.message.reply_text(get_message(lang, 'choose_time'), reply_markup=time_keyboard(lang))
        return CHOOSE_TIME
    except Exception as e:
        logger.error(f"Error in choose_chapter: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return ConversationHandler.END

async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        time_text = update.message.text.strip()
        minutes = int(time_text.split()[0])
        context.user_data['temp_time'] = minutes
        await update.message.reply_text(get_message(lang, 'confirm_read'), reply_markup=confirm_keyboard(lang))
        return CONFIRM_READ
    except Exception as e:
        logger.error(f"Error in choose_time: {e}")
        await update.message.reply_text(get_message(lang, 'invalid_time'))
        return CHOOSE_TIME

async def confirm_read(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        lang = context.user_data.get('lang', 'en')
        await query.edit_message_text(text=get_message(lang, 'enter_note'))
        return ENTER_NOTE
    except Exception as e:
        logger.error(f"Error in confirm_read: {e}")
        await query.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return ConversationHandler.END

async def enter_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        note = update.message.text.strip()
        if note.lower() == 'none' or note == 'هیچ':
            note = None
        user_id = update.effective_user.id
        grade = context.user_data.get('grade', '10')
        subject = context.user_data.pop('temp_subject', None)
        chapter = context.user_data.pop('temp_chapter', None)
        minutes = context.user_data.pop('temp_time', 0)
        async with db_pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO lesson_logs (user_id, grade, subject, chapter, minutes, note, date) VALUES ($1, $2, $3, $4, $5, $6, CURRENT_DATE)',
                user_id, grade, subject, chapter, minutes, note
            )
        await update.message.reply_text(get_message(lang, 'lesson_logged'), reply_markup=main_menu_keyboard(lang))
        return MAIN
    except Exception as e:
        logger.error(f"Error in enter_note: {e}")
        await update.message.reply_text(get_message(lang, 'error'))
        return MAIN

async def view_report(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        grade = context.user_data.get('grade', '10')
        user_id = update.effective_user.id
        key = 'en_' + grade if lang == 'en' else grade
        subjects = subjects_by_grade.get(key, [])
        report = get_message(lang, 'report_title') + "\n\n"
        report += get_message(lang, 'subjects_to_study') + "\n" + "\n".join(subjects) + "\n\n"
        
        async with db_pool.acquire() as conn:
            total_time = await conn.fetchval('SELECT SUM(minutes) FROM lesson_logs WHERE user_id = $1', user_id) or 0
            notes_rows = await conn.fetch('SELECT note FROM lesson_logs WHERE user_id = $1 AND note IS NOT NULL', user_id)
        
        report += get_message(lang, 'total_time').format(total=total_time) + "\n\n"
        if notes_rows:
            report += get_message(lang, 'notes') + "\n" + "\n".join([row['note'] for row in notes_rows]) + "\n"
        else:
            report += get_message(lang, 'notes') + "\n" + get_message(lang, 'no_data') + "\n"
        
        await update.message.reply_text(report, reply_markup=main_menu_keyboard(lang))
        return MAIN
    except Exception as e:
        logger.error(f"Error in view_report: {e}")
        await update.message.reply_text(get_message(lang, 'error'))
        return MAIN

async def log_study_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        subject = update.message.text.strip()
        if not subject:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_STUDY_SUBJECT
        context.user_data['temp_subject'] = subject
        await update.message.reply_text(get_message(lang, 'enter_time'))
        return LOG_STUDY_TIME
    except Exception as e:
        logger.error(f"Error in log_study_subject: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return ConversationHandler.END

async def log_study_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
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
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return MAIN

async def log_test_subject(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
        subject = update.message.text.strip()
        if not subject:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_TEST_SUBJECT
        context.user_data['temp_subject'] = subject
        await update.message.reply_text(get_message(lang, 'enter_test_count'))
        return LOG_TEST_COUNT
    except Exception as e:
        logger.error(f"Error in log_test_subject: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return ConversationHandler.END

async def log_test_count(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data.get('lang', 'en')
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
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))
        return MAIN

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    try:
        async with db_pool.acquire() as conn:
            user_count = await conn.fetchval('SELECT COUNT(*) FROM users')
            total_hours = await conn.fetchval('SELECT SUM(minutes)/60 FROM study_logs') or 0
            total_tests = await conn.fetchval('SELECT SUM(count) FROM test_logs') or 0
            total_lesson_minutes = await conn.fetchval('SELECT SUM(minutes) FROM lesson_logs') or 0
        await update.message.reply_text(
            f"📊 Stats:\n👥 Total users: {user_count}\n⏰ Total study hours: {total_hours}\n🧪 Total tests: {total_tests}\n📚 Total lesson minutes: {total_lesson_minutes}"
        )
    except Exception as e:
        logger.error(f"Error in stats: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    try:
        async with db_pool.acquire() as conn:
            users = await conn.fetch('SELECT * FROM users')
            study_logs = await conn.fetch('SELECT * FROM study_logs')
            test_logs = await conn.fetch('SELECT * FROM test_logs')
            lesson_logs = await conn.fetch('SELECT * FROM lesson_logs')
        backup_str = f"Users:\n{users}\n\nStudy Logs:\n{study_logs}\n\nTest Logs:\n{test_logs}\n\nLesson Logs:\n{lesson_logs}"
        buf = StringIO(backup_str)
        buf.seek(0)
        await update.message.reply_document(document=buf, filename='backup.txt')
    except Exception as e:
        logger.error(f"Error in backup: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))

async def clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    try:
        async with db_pool.acquire() as conn:
            await conn.execute('DELETE FROM lesson_logs')
            await conn.execute('DELETE FROM study_logs')
            await conn.execute('DELETE FROM test_logs')
            await conn.execute('DELETE FROM users')
        await update.message.reply_text("✅ Database cleared.")
    except Exception as e:
        logger.error(f"Error in clear_db: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'error'))

conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        CHOOSE_LANG: [CallbackQueryHandler(choose_lang, pattern='^lang_')],
        ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
        ENTER_GRADE: [CallbackQueryHandler(enter_grade, pattern='^grade_'), MessageHandler(filters.TEXT & ~filters.COMMAND, enter_grade)],
        MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_message)],
        LOG_STUDY_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_study_subject)],
        LOG_STUDY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_study_time)],
        LOG_TEST_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_test_subject)],
        LOG_TEST_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_test_count)],
        CHOOSE_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_subject)],
        CHOOSE_CHAPTER: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_chapter)],
        CHOOSE_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, choose_time)],
        CONFIRM_READ: [CallbackQueryHandler(confirm_read, pattern='^read_confirm')],
        ENTER_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_note)],
        VIEW_REPORT: [MessageHandler(filters.TEXT & ~filters.COMMAND, view_report)],
    },
    fallbacks=[],
)

application.add_handler(conv_handler)
application.add_handler(CommandHandler('stats', stats))
application.add_handler(CommandHandler('backup', backup))
application.add_handler(CommandHandler('clear_db', clear_db))

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
        db_pool = await asyncpg.create_pool(dsn=DB_URL, min_size=1, max_size=10)
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    language TEXT NOT NULL,
                    grade TEXT NOT NULL
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS study_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    subject TEXT NOT NULL,
                    minutes INTEGER NOT NULL
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS test_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    date DATE NOT NULL,
                    subject TEXT NOT NULL,
                    count INTEGER NOT NULL
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS lesson_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
                    grade TEXT NOT NULL,
                    subject TEXT NOT NULL,
                    chapter TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    note TEXT,
                    date DATE NOT NULL
                )
            ''')
        logger.info("Database tables created successfully")
        
        commands = [BotCommand("start", "Start the bot 🚀")]
        await application.bot.set_my_commands(commands)
        
        await application.bot.set_webhook(url=WEBHOOK_URL)
        logger.info(f"Webhook set: {WEBHOOK_URL}")
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
