import os
import logging
import asyncpg
from io import BytesIO, StringIO
from datetime import date
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from matplotlib import font_manager
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
ADMIN_ID = 5542927340

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
CHOOSE_LANG, ENTER_NAME, SELECT_GRADE, MAIN, LOG_STUDY_SUBJECT, LOG_STUDY_TIME, LOG_TEST_SUBJECT, LOG_TEST_COUNT, MY_LESSONS, SELECT_LESSON, SELECT_CHAPTER, SELECT_STUDY_TIME, ADD_NOTE = range(13)

db_pool = None

# دیتابیس دروس بر اساس پایه
LESSONS_DATA = {
    'دهم': {
        'شیمی': ['فصل ۱: کیهان زادگاه الفبای هستی', 'فصل ۲: ردپای گازها در زندگی', 'فصل ۳: آب، آهنگ زندگی'],
        'ریاضی': ['فصل ۱: مجموعه، الگو و دنباله', 'فصل ۲: مثلثات', 'فصل ۳: توان های گویا', 'فصل ۴: معادله و تابع'],
        'فیزیک': ['فصل ۱: فیزیک و اندازه گیری', 'فصل ۲: کار، انرژی و توان', 'فصل ۳: ویژگی های فیزیکی مواد'],
        'زیست': ['فصل ۱: زیست شناسی دیروز، امروز و فردا', 'فصل ۲: گوارش و جذب مواد', 'فصل ۳: تبادلات گازی']
    },
    'یازدهم': {
        'شیمی': ['فصل ۱: قدر هدایای زمینی را بدانیم', 'فصل ۲: در پی غذای سالم', 'فصل ۳: پوشاک نیازی پایان ناپذیر'],
        'ریاضی': ['فصل ۱: هندسه تحلیلی', 'فصل ۲: تابع', 'فصل ۳: مثلثات', 'فصل ۴: حد و پیوستگی'],
        'فیزیک': ['فصل ۱: الکتریسیته ساکن', 'فصل ۲: جریان الکتریکی', 'فصل ۳: مغناطیس'],
        'زیست': ['فصل ۱: تنظیم عصبی', 'فصل ۲: حواس', 'فصل ۳: دستگاه حرکتی', 'فصل ۴: تنظیم شیمیایی'],
        'زمین شناسی': ['فصل ۱: آفرینش کیهان و جهان', 'فصل ۲: منابع معدنی', 'فصل ۳: منابع آب و خاک']
    },
    'دوازدهم': {
        'شیمی': ['فصل ۱: مولکول ها در خدمت تندرستی', 'فصل ۲: آسایش و رفاه در سایه شیمی', 'فصل ۳: شیمی جلوه ای از هنر'],
        'ریاضی': ['فصل ۱: احتمال', 'فصل ۲: آمار', 'فصل ۳: دنباله حسابی و هندسی', 'فصل ۴: حسابان'],
        'فیزیک': ['فصل ۱: حرکت بر خط راست', 'فصل ۲: دینامیک', 'فصل ۳: نوسان و امواج'],
        'زیست': ['فصل ۱: مولکول های اطلاعاتی', 'فصل ۲: جریان اطلاعات در یاخته', 'فصل ۳: انتقال اطلاعات در نسل ها']
    }
}

def get_message(lang, key):
    messages = {
        'en': {
            'choose_lang': "🌍 Choose language:",
            'enter_name': "📝 Enter your name:",
            'select_grade': "🎓 Select your grade:",
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
            'no_data': "📉 No data available for the chart.",
            'study_chart_title': "📚 Study Hours (Last 7 Days)",
            'test_chart_title': "🧪 Tests Taken (Last 7 Days)",
            'date_label': "📅 Date",
            'hours_label': "⏰ Hours",
            'count_label': "🔢 Count",
            'my_lessons': "📚 My Lessons",
            'select_lesson': "📖 Select a lesson:",
            'select_chapter': "📚 Select a chapter:",
            'select_study_time': "⏰ Select study time:",
            'study_completed': "✅ Study completed!",
            'add_note': "📝 Do you have any notes? (e.g., read half of it)",
            'note_saved': "📝 Note saved successfully!",
            'study_summary': "📊 Study Summary",
            'no_lessons': "📚 No lessons available for your grade.",
        },
        'fa': {
            'choose_lang': "🌍 زبان را انتخاب کنید:",
            'enter_name': "📝 نام خود را وارد کنید:",
            'select_grade': "🎓 پایه تحصیلی خود را انتخاب کنید:",
            'welcome_back': "👋 خوش آمدید به درس من، {name}! 📚",
            'saved': "✅ پروفایل شما ذخیره شد! 🎉",
            'main_menu': "📋 منوی اصلی",
            'enter_subject': "📖 درس را وارد کنید:",
            'enter_time': "⏱️ زمان مطالعه را به دقیقه وارد کنید:",
            'invalid_time': "❌ زمان نامعتبر. لطفا عدد وارد کنید.",
            'logged': "✅ مطالعه ثبت شد! 📈",
            'enter_test_count': "🧪 تعداد تست‌ها را وارد کنید:",
            'invalid_count': "❌ تعداد نامعتبر. لطفا عدد وارد کنید.",
            'tests_logged': "✅ تست‌ها ثبت شد! 📊",
            'no_data': "📉 داده‌ای برای نمودار موجود نیست.",
            'study_chart_title': "📚 ساعات مطالعه (۷ روز اخیر)",
            'test_chart_title': "🧪 تست‌های زده‌شده (۷ روز اخیر)",
            'date_label': "📅 تاریخ",
            'hours_label': "⏰ ساعات",
            'count_label': "🔢 تعداد",
            'my_lessons': "📚 درس های من",
            'select_lesson': "📖 درس مورد نظر را انتخاب کنید:",
            'select_chapter': "📚 فصل مورد نظر را انتخاب کنید:",
            'select_study_time': "⏰ زمان مطالعه را انتخاب کنید:",
            'study_completed': "✅ مطالعه تکمیل شد!",
            'add_note': "📝 یادداشتی دارید؟ (مثلاً نصفشو خوندم)",
            'note_saved': "📝 یادداشت ثبت شد!",
            'study_summary': "📊 خلاصه مطالعه",
            'no_lessons': "📚 درسی برای پایه شما موجود نیست.",
        }
    }
    return messages.get(lang, messages['en']).get(key, "")

def lang_keyboard():
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("🇮🇷 فارسی", callback_data='lang_fa'), InlineKeyboardButton("🇬🇧 English", callback_data='lang_en')]
    ])

def grade_keyboard(lang):
    grades = ["دهم", "یازدهم", "دوازدهم"] if lang == 'fa' else ["10th", "11th", "12th"]
    keyboard = [[InlineKeyboardButton(grade, callback_data=f'grade_{grade}') for grade in grades]]
    return InlineKeyboardMarkup(keyboard)

def main_menu_keyboard(lang):
    keyboard = [
        [KeyboardButton("📚 ثبت مطالعه" if lang == 'fa' else "📚 Log Study")],
        [KeyboardButton("📚 درس های من" if lang == 'fa' else "📚 My Lessons")],
        [KeyboardButton("📈 نمودار مطالعه" if lang == 'fa' else "📈 View Study Chart")],
        [KeyboardButton("🧪 ثبت تست" if lang == 'fa' else "🧪 Log Test")],
        [KeyboardButton("📊 نمودار تست" if lang == 'fa' else "📊 View Test Chart")],
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=False)

def lessons_keyboard(grade, lang):
    if grade not in LESSONS_DATA:
        return None
    lessons = list(LESSONS_DATA[grade].keys())
    keyboard = []
    for lesson in lessons:
        keyboard.append([InlineKeyboardButton(lesson, callback_data=f'lesson_{lesson}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت" if lang == 'fa' else "🔙 Back", callback_data='back_to_main')])
    return InlineKeyboardMarkup(keyboard)

def chapters_keyboard(grade, lesson, lang):
    if grade not in LESSONS_DATA or lesson not in LESSONS_DATA[grade]:
        return None
    chapters = LESSONS_DATA[grade][lesson]
    keyboard = []
    for i, chapter in enumerate(chapters, 1):
        keyboard.append([InlineKeyboardButton(chapter, callback_data=f'chapter_{i}')])
    keyboard.append([InlineKeyboardButton("🔙 بازگشت" if lang == 'fa' else "🔙 Back", callback_data='back_to_lessons')])
    return InlineKeyboardMarkup(keyboard)

def study_time_keyboard(lang):
    times = [10, 20, 30, 45, 60, 90, 120]
    keyboard = []
    row = []
    for time in times:
        row.append(InlineKeyboardButton(f"{time} دقیقه" if lang == 'fa' else f"{time} min", callback_data=f'time_{time}'))
        if len(row) == 2:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("🔙 بازگشت" if lang == 'fa' else "🔙 Back", callback_data='back_to_chapters')])
    return InlineKeyboardMarkup(keyboard)

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
            ax.set_title(get_message(lang, title_key)[::-1] if 'fa' in lang else get_message(lang, title_key), fontsize=14)
            ax.set_xlabel(get_message(lang, 'date_label')[::-1] if 'fa' in lang else get_message(lang, 'date_label'), fontsize=12)
            ax.set_ylabel(get_message(lang, label)[::-1] if 'fa' in lang else get_message(lang, label), fontsize=12)
        
        buf = BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        buf.seek(0)
        plt.close(fig)
        return buf, None
    except Exception as e:
        logger.error(f"Error generating chart: {e}")
        return None, get_message(lang, 'no_data')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = update.effective_user.id
        logger.info(f"Start command received from user_id: {user_id}")
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
        await update.message.reply_text(get_message(lang, 'select_grade'), reply_markup=grade_keyboard(lang))
        return SELECT_GRADE
    except Exception as e:
        logger.error(f"Error in enter_name: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
        return ConversationHandler.END

async def select_grade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        grade = query.data.split('_')[1]
        context.user_data['grade'] = grade
        
        lang = context.user_data['lang']
        name = context.user_data['name']
        user_id = update.effective_user.id
        
        async with db_pool.acquire() as conn:
            await conn.execute(
                'INSERT INTO users (id, name, language, grade) VALUES ($1, $2, $3, $4)',
                user_id, name, lang, grade
            )
        
        await query.edit_message_text(
            text=get_message(lang, 'saved'), 
            reply_markup=main_menu_keyboard(lang)
        )
        
        # اطلاع‌رسانی به ادمین
        await context.bot.send_message(
            ADMIN_ID, 
            f"👤 کاربر جدید: {name} (ID: {user_id}, پایه: {grade})"
        )
        
        return MAIN
    except Exception as e:
        logger.error(f"Error in select_grade: {e}")
        return ConversationHandler.END

async def main_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data['lang']
        text = update.message.text
        
        if text in ["📚 ثبت مطالعه", "📚 Log Study"]:
            await update.message.reply_text(get_message(lang, 'enter_subject'))
            return LOG_STUDY_SUBJECT
        elif text in ["📚 درس های من", "📚 My Lessons"]:
            grade = context.user_data.get('grade')
            if not grade or grade not in LESSONS_DATA:
                await update.message.reply_text(get_message(lang, 'no_lessons'), reply_markup=main_menu_keyboard(lang))
                return MAIN
            
            await update.message.reply_text(
                get_message(lang, 'select_lesson'),
                reply_markup=lessons_keyboard(grade, lang)
            )
            return MY_LESSONS
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
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
        return MAIN

async def my_lessons(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_main':
            lang = context.user_data['lang']
            await query.edit_message_text(
                get_message(lang, 'main_menu'),
                reply_markup=main_menu_keyboard(lang)
            )
            return MAIN
        
        elif query.data.startswith('lesson_'):
            lesson = query.data.split('_')[1]
            context.user_data['selected_lesson'] = lesson
            lang = context.user_data['lang']
            grade = context.user_data.get('grade')
            
            await query.edit_message_text(
                f"{get_message(lang, 'select_chapter')}\n📖 {lesson}",
                reply_markup=chapters_keyboard(grade, lesson, lang)
            )
            return SELECT_CHAPTER
    
    except Exception as e:
        logger.error(f"Error in my_lessons: {e}")
    return MAIN

async def select_chapter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_lessons':
            lang = context.user_data['lang']
            grade = context.user_data.get('grade')
            await query.edit_message_text(
                get_message(lang, 'select_lesson'),
                reply_markup=lessons_keyboard(grade, lang)
            )
            return MY_LESSONS
        
        elif query.data.startswith('chapter_'):
            chapter_index = int(query.data.split('_')[1]) - 1
            lesson = context.user_data['selected_lesson']
            grade = context.user_data.get('grade')
            
            if grade in LESSONS_DATA and lesson in LESSONS_DATA[grade]:
                chapters = LESSONS_DATA[grade][lesson]
                if 0 <= chapter_index < len(chapters):
                    context.user_data['selected_chapter'] = chapters[chapter_index]
                    lang = context.user_data['lang']
                    
                    await query.edit_message_text(
                        f"{get_message(lang, 'select_study_time')}\n📚 {chapters[chapter_index]}",
                        reply_markup=study_time_keyboard(lang)
                    )
                    return SELECT_STUDY_TIME
    
    except Exception as e:
        logger.error(f"Error in select_chapter: {e}")
    return MAIN

async def select_study_time(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        query = update.callback_query
        await query.answer()
        
        if query.data == 'back_to_chapters':
            lesson = context.user_data['selected_lesson']
            lang = context.user_data['lang']
            grade = context.user_data.get('grade')
            
            await query.edit_message_text(
                f"{get_message(lang, 'select_chapter')}\n📖 {lesson}",
                reply_markup=chapters_keyboard(grade, lesson, lang)
            )
            return SELECT_CHAPTER
        
        elif query.data.startswith('time_'):
            minutes = int(query.data.split('_')[1])
            context.user_data['study_minutes'] = minutes
            
            # ذخیره مطالعه
            user_id = update.effective_user.id
            lesson = context.user_data['selected_lesson']
            chapter = context.user_data['selected_chapter']
            
            async with db_pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO study_logs (user_id, date, subject, minutes, chapter, grade) VALUES ($1, CURRENT_DATE, $2, $3, $4, $5)',
                    user_id, lesson, minutes, chapter, context.user_data.get('grade')
                )
            
            lang = context.user_data['lang']
            
            # نمایش خلاصه مطالعه
            summary = f"""
{get_message(lang, 'study_summary')}
📖 {lesson}
📚 {chapter}
⏰ {minutes} {get_message(lang, 'minutes') if lang == 'en' else 'دقیقه'}
✅ {get_message(lang, 'study_completed')}
"""
            await query.edit_message_text(summary)
            
            # پرسش برای یادداشت
            await context.bot.send_message(
                chat_id=update.effective_chat.id,
                text=get_message(lang, 'add_note'),
                reply_markup=ReplyKeyboardMarkup([
                    [KeyboardButton("✅ ثبت بدون یادداشت" if lang == 'fa' else "✅ Save without note")],
                    [KeyboardButton("📝 افزودن یادداشت" if lang == 'fa' else "📝 Add note")]
                ], resize_keyboard=True, one_time_keyboard=True)
            )
            return ADD_NOTE
    
    except Exception as e:
        logger.error(f"Error in select_study_time: {e}")
    return MAIN

async def add_note(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        lang = context.user_data['lang']
        text = update.message.text
        
        if text in ["✅ ثبت بدون یادداشت", "✅ Save without note"]:
            await update.message.reply_text(
                get_message(lang, 'logged'),
                reply_markup=main_menu_keyboard(lang)
            )
            return MAIN
        
        elif text in ["📝 افزودن یادداشت", "📝 Add note"]:
            await update.message.reply_text(get_message(lang, 'add_note'))
            return ADD_NOTE
        
        else:
            # ذخیره یادداشت
            user_id = update.effective_user.id
            note = update.message.text
            
            async with db_pool.acquire() as conn:
                await conn.execute(
                    'INSERT INTO study_notes (user_id, date, lesson, chapter, note) VALUES ($1, CURRENT_DATE, $2, $3, $4)',
                    user_id, context.user_data.get('selected_lesson'), context.user_data.get('selected_chapter'), note
                )
            
            await update.message.reply_text(
                get_message(lang, 'note_saved'),
                reply_markup=main_menu_keyboard(lang)
            )
            return MAIN
    
    except Exception as e:
        logger.error(f"Error in add_note: {e}")
        await update.message.reply_text(get_message(context.user_data.get('lang', 'en'), 'no_data'))
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

async def stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    async with db_pool.acquire() as conn:
        user_count = await conn.fetchval('SELECT COUNT(*) FROM users')
        total_hours = await conn.fetchval('SELECT SUM(minutes)/60 FROM study_logs') or 0
        total_tests = await conn.fetchval('SELECT SUM(count) FROM test_logs') or 0
    await update.message.reply_text(f"📊 Stats:\n👥 Total users: {user_count}\n⏰ Total study hours: {total_hours}\n🧪 Total tests: {total_tests}")

async def backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    async with db_pool.acquire() as conn:
        users = await conn.fetch('SELECT * FROM users')
        study_logs = await conn.fetch('SELECT * FROM study_logs')
        test_logs = await conn.fetch('SELECT * FROM test_logs')
        study_notes = await conn.fetch('SELECT * FROM study_notes')
    backup_str = f"Users:\n{users}\n\nStudy Logs:\n{study_logs}\n\nTest Logs:\n{test_logs}\n\nStudy Notes:\n{study_notes}"
    buf = StringIO(backup_str)
    buf.seek(0)
    await update.message.reply_document(document=buf, filename='backup.txt')

async def clear_db(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("❌ Access denied.")
        return
    async with db_pool.acquire() as conn:
        await conn.execute('DELETE FROM study_notes')
        await conn.execute('DELETE FROM study_logs')
        await conn.execute('DELETE FROM test_logs')
        await conn.execute('DELETE FROM users')
    await update.message.reply_text("✅ Database cleared.")

# تنظیم handlerهای کانورسیشن
conv_handler = ConversationHandler(
    entry_points=[CommandHandler('start', start)],
    states={
        CHOOSE_LANG: [CallbackQueryHandler(choose_lang, pattern='^lang_')],
        ENTER_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, enter_name)],
        SELECT_GRADE: [CallbackQueryHandler(select_grade, pattern='^grade_')],
        MAIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, main_message)],
        MY_LESSONS: [CallbackQueryHandler(my_lessons, pattern='^(lesson_|back_to_main)')],
        SELECT_CHAPTER: [CallbackQueryHandler(select_chapter, pattern='^(chapter_|back_to_lessons)')],
        SELECT_STUDY_TIME: [CallbackQueryHandler(select_study_time, pattern='^(time_|back_to_chapters)')],
        ADD_NOTE: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_note)],
        LOG_STUDY_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_study_subject)],
        LOG_STUDY_TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_study_time)],
        LOG_TEST_SUBJECT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_test_subject)],
        LOG_TEST_COUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, log_test_count)],
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
        db_pool = await asyncpg.create_pool(dsn=DB_URL)
        async with db_pool.acquire() as conn:
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id BIGINT PRIMARY KEY,
                    name TEXT NOT NULL,
                    language TEXT NOT NULL,
                    grade TEXT
                )
            ''')
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS study_logs (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id),
                    date DATE NOT NULL,
                    subject TEXT NOT NULL,
                    minutes INTEGER NOT NULL,
                    chapter TEXT,
                    grade TEXT
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
            await conn.execute('''
                CREATE TABLE IF NOT EXISTS study_notes (
                    id SERIAL PRIMARY KEY,
                    user_id BIGINT REFERENCES users(id),
                    date DATE NOT NULL,
                    lesson TEXT NOT NULL,
                    chapter TEXT NOT NULL,
                    note TEXT
                )
            ''')
        logger.info("Database tables created successfully")
        
        # تنظیم منوی بات
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
        await db_pool.close()
        logger.info("Application shutdown successfully")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8000)))
