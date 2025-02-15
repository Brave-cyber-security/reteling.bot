from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, CallbackQuery
import asyncio
import logging
import aiosqlite
from dotenv import load_dotenv
import os
import sys
from datetime import datetime
import pytz


load_dotenv()
TOKEN = os.getenv("TOKEN")
if not TOKEN:
    print("Error: Bot token not found in environment variables. Please set TOKEN in .env file.")
    sys.exit(1)

TEACHER_ID = os.getenv("TEACHER_ID")
if not TEACHER_ID:
    print("Error: Teacher ID not found in environment variables. Please set TEACHER_ID in .env file.")
    sys.exit(1)

try:
    TEACHER_ID = int(TEACHER_ID)
except ValueError:
    print("Error: TEACHER_ID must be a valid integer.")
    sys.exit(1)

GROUPS = [
    "101", "102", "103",
    "201", "202", "203", "204", "205", "206", "207", "208", 
    "209", "210", "211", "212", "213", "214", "215", "246"
]

bot = Bot(token=TOKEN)
dp = Dispatcher()

message_student_map = {}
user_topics = {}

class RegistrationStates:
    WAITING_FOR_FULL_NAME = "waiting_for_full_name"
    WAITING_FOR_GROUP = "waiting_for_group"
    WAITING_FOR_TOPIC = "waiting_for_topic"
    WAITING_FOR_GRADE = "waiting_for_grade"

registration_state = {}
temp_data = {}

async def init_db():
    async with aiosqlite.connect("mydatabase.db") as db:
        await db.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            full_name TEXT NOT NULL,
            username TEXT,
            group_name TEXT NOT NULL,
            current_topic TEXT
        )
        """)

        await db.execute("""
        CREATE TABLE IF NOT EXISTS grades (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            topic TEXT NOT NULL,
            grade INTEGER NOT NULL,
            feedback TEXT,
            date TIMESTAMP NOT NULL,
            FOREIGN KEY (user_id) REFERENCES users(user_id)
        )
        """)
        
        await db.commit()

def create_group_keyboard(page=0, items_per_page=8):
    groups = GROUPS[page * items_per_page:(page + 1) * items_per_page]
    keyboard = []
    row = []
    
    for i, group in enumerate(groups):
        row.append(InlineKeyboardButton(text=group, callback_data=f"group_{group}"))
        if len(row) == 2 or i == len(groups) - 1:
            keyboard.append(row)
            row = []
    
    navigation = []
    if page > 0:
        navigation.append(InlineKeyboardButton(text="⬅️ Orqaga", callback_data=f"page_{page-1}"))
    if (page + 1) * items_per_page < len(GROUPS):
        navigation.append(InlineKeyboardButton(text="Oldinga ➡️", callback_data=f"page_{page+1}"))
    
    if navigation:
        keyboard.append(navigation)
    
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

def create_confirm_keyboard(group):
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text="✅ Ha", callback_data=f"confirm_group_{group}"),
                InlineKeyboardButton(text="❌ Yo'q", callback_data="cancel_group")
            ]
        ]
    )

def create_statistics_keyboard():
    keyboard = []
    row = []
    
    for i, group in enumerate(GROUPS):
        row.append(InlineKeyboardButton(text=group, callback_data=f"stats_{group}"))
        if len(row) == 3 or i == len(GROUPS) - 1:
            keyboard.append(row)
            row = []
            
    return InlineKeyboardMarkup(inline_keyboard=keyboard)

@dp.message(Command("start"))
async def start_handler(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("mydatabase.db") as db:
        async with db.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)) as cursor:
            user = await cursor.fetchone()

    if user_id == TEACHER_ID:
        stats_keyboard = create_statistics_keyboard()
        await message.answer(
            "Assalomu alaykum, ustoz! Botga xush kelibsiz.\n"
            "Guruh bo'yicha statistikani ko'rish uchun guruhni tanlang:",
            reply_markup=stats_keyboard
        )
    elif user:
        registration_state[user_id] = RegistrationStates.WAITING_FOR_TOPIC
        await message.answer(
            "Assalomu alaykum! Siz allaqachon ro'yxatdan o'tibsiz.\n"
            "Retelling topshirish uchun yangi mavzu kiriting:"
        )
    else:
        registration_state[user_id] = RegistrationStates.WAITING_FOR_FULL_NAME
        await message.answer("Ism-familiyangizni kiriting:")

@dp.message()
async def handle_messages(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in registration_state:
        await message.answer("Iltimos, /start buyrug'ini yuboring.")
        return

    current_state = registration_state.get(user_id)

    if current_state == RegistrationStates.WAITING_FOR_FULL_NAME:
        await process_full_name(message)
    elif current_state == RegistrationStates.WAITING_FOR_TOPIC:
        await process_topic(message)
    elif message.video_note:
        await handle_video(message)

async def process_full_name(message: types.Message):
    user_id = message.from_user.id
    full_name = message.text.strip()

    if not full_name:
        await message.answer("Ism familiya kiritilmadi. Iltimos, qaytadan urinib ko'ring.")
        return

    temp_data[user_id] = {"full_name": full_name}
    registration_state[user_id] = RegistrationStates.WAITING_FOR_GROUP
    group_keyboard = create_group_keyboard()
    await message.answer("Guruhingizni tanlang:", reply_markup=group_keyboard)

@dp.callback_query(lambda c: c.data.startswith('page_'))
async def process_page(callback_query: CallbackQuery):
    page = int(callback_query.data.split('_')[1])
    await callback_query.message.edit_reply_markup(reply_markup=create_group_keyboard(page))
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith('group_'))
async def process_group_selection(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    group = callback_query.data.split('_')[1]
    
    confirm_keyboard = create_confirm_keyboard(group)
    await callback_query.message.edit_text(
        f"Siz {group}-guruhni tanladingiz.\nShu guruhda o'qiysizmi?",
        reply_markup=confirm_keyboard
    )
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith('confirm_group_'))
async def process_group_confirmation(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    group = callback_query.data.split('_')[2]
    
    if user_id not in temp_data:
        await callback_query.message.answer("Xatolik yuz berdi. /start buyrug'ini qayta yuboring.")
        return

    full_name = temp_data[user_id]["full_name"]
    
    async with aiosqlite.connect("mydatabase.db") as db:
        await db.execute("""
        INSERT INTO users (user_id, full_name, username, group_name, current_topic)
        VALUES (?, ?, ?, ?, ?)
        """, (user_id, full_name, callback_query.from_user.username, group, None))
        await db.commit()

    registration_state[user_id] = RegistrationStates.WAITING_FOR_TOPIC
    await callback_query.message.edit_text(
        f"Ro'yxatdan o'tdingiz!\n"
        f"Ism familiya: {full_name}\n"
        f"Guruh: {group}\n\n"
        "Endi retelling mavzusini kiriting:"
    )
    del temp_data[user_id]
    await callback_query.answer()

@dp.callback_query(lambda c: c.data == "cancel_group")
async def process_group_cancellation(callback_query: CallbackQuery):
    user_id = callback_query.from_user.id
    group_keyboard = create_group_keyboard()
    await callback_query.message.edit_text("Guruhingizni tanlang:", reply_markup=group_keyboard)
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith('stats_'))
async def show_group_statistics(callback_query: CallbackQuery):
    if callback_query.from_user.id != TEACHER_ID:
        await callback_query.answer("Bu funksiya faqat o'qituvchi uchun!")
        return

    group = callback_query.data.split('_')[1]
    
    async with aiosqlite.connect("mydatabase.db") as db:
        async with db.execute("""
            SELECT u.full_name, u.user_id, 
                   COUNT(g.grade) as total_retellings,
                   SUM(CASE WHEN g.grade = 5 THEN 1 ELSE 0 END) as grade_5,
                   SUM(CASE WHEN g.grade = 4 THEN 1 ELSE 0 END) as grade_4,
                   SUM(CASE WHEN g.grade = 3 THEN 1 ELSE 0 END) as grade_3,
                   SUM(CASE WHEN g.grade = 2 THEN 1 ELSE 0 END) as grade_2,
                   SUM(CASE WHEN g.grade = 1 THEN 1 ELSE 0 END) as grade_1
            FROM users u
            LEFT JOIN grades g ON u.user_id = g.user_id
            WHERE u.group_name = ?
            GROUP BY u.user_id
            ORDER BY u.full_name
        """, (group,)) as cursor:
            students = await cursor.fetchall()

    if not students:
        await callback_query.message.answer(f"{group}-guruhda hali o'quvchilar yo'q.")
        return

    stats_message = f"📊 {group}-guruh statistikasi:\n\n"
    
    for student in students:
        name, _, total, grade5, grade4, grade3, grade2, grade1 = student
        grades_info = (
            f"👤 {name}\n"
            f"Jami topshirgan: {total or 0} ta\n"
            f"5 baho: {grade5 or 0} ta\n"
            f"4 baho: {grade4 or 0} ta\n"
            f"3 baho: {grade3 or 0} ta\n"
            f"2 baho: {grade2 or 0} ta\n"
            f"1 baho: {grade1 or 0} ta\n"
            f"{'─' * 30}\n"
        )
        stats_message += grades_info

    await callback_query.message.answer(stats_message)
    await callback_query.answer()

# ... (previous code remains the same)

async def process_topic(message: types.Message):
    user_id = message.from_user.id
    topic = message.text.strip()

    if not topic:
        await message.answer("Mavzu kiritilmadi. Iltimos, mavzuni kiriting:")
        return

    async with aiosqlite.connect("mydatabase.db") as db:
        await db.execute("""
        UPDATE users SET current_topic = ? WHERE user_id = ?
        """, (topic, user_id))
        await db.commit()

    user_topics[user_id] = topic
    registration_state[user_id] = None
    await message.answer(
        f"Retelling mavzusi qabul qilindi: {topic}\n\n"
        "Endi shu mavzu bo'yicha video xabar yuborishingiz mumkin.\n"
        "⚠️ Video yuborilgandan so'ng mavzu o'chirilib, yangi mavzu kiritishingiz kerak bo'ladi."
    )

@dp.message(F.video_note)
async def handle_video(message: types.Message):
    user_id = message.from_user.id
    async with aiosqlite.connect("mydatabase.db") as db:
        async with db.execute("""
            SELECT full_name, group_name, current_topic 
            FROM users 
            WHERE user_id = ?
        """, (user_id,)) as cursor:
            user = await cursor.fetchone()

    if not user:
        await message.answer(
            "Siz ro'yxatdan o'tmagansiz. Iltimos, /start buyrug'ini yuborib ro'yxatdan o'ting."
        )
        return

    if not user[2]:  # current_topic is None
        registration_state[user_id] = RegistrationStates.WAITING_FOR_TOPIC
        await message.answer(
            "Avval retelling mavzusini kiriting.\n"
            "Mavzuni kiriting:"
        )
        return

    tz_tashkent = pytz.timezone('Asia/Tashkent')
    tashkent_time = message.date.astimezone(tz_tashkent)
    formatted_date = tashkent_time.strftime("%d.%m.%Y")
    formatted_time = tashkent_time.strftime("%H:%M")

    student_info = (
        f"📝 Yangi video retelling\n\n"
        f"👤 O'quvchi: {user[0]}\n"
        f"👥 Guruh: {user[1]}\n"
        f"📚 Mavzu: {user[2]}\n"
        f"🔗 Username: @{message.from_user.username}\n"
        f"📅 Sana: {formatted_date}\n"
        f"⏰ Vaqt: {formatted_time}"
    )

    grade_keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text=f"{i} ⭐️", 
                    callback_data=f"grade_{message.message_id}_{i}"
                ) for i in range(5, 0, -1)
            ]
        ]
    )

    try:
        await bot.send_chat_action(chat_id=TEACHER_ID, action="typing")
        teacher_msg = await bot.send_message(
            TEACHER_ID,
            f"{student_info}\n\n💫 Baho qo'yish uchun tanlang:",
            reply_markup=grade_keyboard
        )
        
        forwarded_msg = await bot.forward_message(
            chat_id=TEACHER_ID,
            from_chat_id=message.chat.id,
            message_id=message.message_id
        )
        
        message_student_map[str(message.message_id)] = {
            "user_id": user_id,
            "topic": user[2],
            "forwarded_msg_id": forwarded_msg.message_id,
            "info_msg_id": teacher_msg.message_id
        }
        
        await message.answer(
            "✅ Video retelling muvaffaqiyatli yuborildi!\n"
            "👨‍🏫 O'qituvchi tekshirgandan so'ng sizga baho va qayta aloqa yuboriladi."
        )

    except Exception as e:
        logging.error(f"Error sending message to teacher: {e}")
        await message.answer(
            "❌ Kechirasiz, texnik nosozlik yuz berdi.\n"
            "Iltimos, qaytadan urinib ko'ring."
        )

@dp.callback_query(lambda c: c.data.startswith('grade_'))
async def process_grade(callback_query: CallbackQuery):
    if callback_query.from_user.id != TEACHER_ID:
        await callback_query.answer("⚠️ Faqat o'qituvchi baho qo'ya oladi!")
        return

    _, message_id, grade = callback_query.data.split('_')
    student_data = message_student_map.get(message_id)
    
    if not student_data:
        await callback_query.answer("❌ Xatolik: Bu retelling topilmadi.")
        return

    grade = int(grade)
    user_id = student_data["user_id"]
    topic = student_data["topic"]
    forwarded_msg_id = student_data["forwarded_msg_id"]
    info_msg_id = student_data["info_msg_id"]

    tz_tashkent = pytz.timezone('Asia/Tashkent')
    current_time = datetime.now(tz_tashkent)

    async with aiosqlite.connect("mydatabase.db") as db:
        # Add grade to database
        await db.execute("""
        INSERT INTO grades (user_id, topic, grade, date)
        VALUES (?, ?, ?, ?)
        """, (user_id, topic, grade, current_time.isoformat()))
        
        # Reset current_topic
        await db.execute("""
        UPDATE users SET current_topic = NULL
        WHERE user_id = ?
        """, (user_id,))
        
        await db.commit()

        # Get student's total grades
        async with db.execute("""
            SELECT 
                COUNT(*) as total,
                SUM(CASE WHEN grade = 5 THEN 1 ELSE 0 END) as grade_5,
                SUM(CASE WHEN grade = 4 THEN 1 ELSE 0 END) as grade_4,
                SUM(CASE WHEN grade = 3 THEN 1 ELSE 0 END) as grade_3,
                SUM(CASE WHEN grade = 2 THEN 1 ELSE 0 END) as grade_2,
                SUM(CASE WHEN grade = 1 THEN 1 ELSE 0 END) as grade_1
            FROM grades 
            WHERE user_id = ?
        """, (user_id,)) as cursor:
            stats = await cursor.fetchone()

    # Send grade and stats to student
    stats_message = (
        f"🎯 Sizning retelling bahoyingiz: {grade} {'⭐️' * grade}\n"
        f"📚 Mavzu: {topic}\n\n"
        f"📊 Sizning umumiy natijalaringiz:\n"
        f"📝 Jami topshirgan retellinglar: {stats[0]}\n"
        f"5 baho: {stats[1] or 0} ta\n"
        f"4 baho: {stats[2] or 0} ta\n"
        f"3 baho: {stats[3] or 0} ta\n"
        f"2 baho: {stats[4] or 0} ta\n"
        f"1 baho: {stats[5] or 0} ta"
    )

    await bot.send_message(user_id, stats_message)

    # Update teacher's message
    await callback_query.message.edit_text(
        f"{callback_query.message.text.split("Baho qo'yish uchun tanlang:")[0]}\n"
        f"✅ Qo'yilgan baho: {grade} {'⭐️' * grade}"
    )

    # Clean up
    try:
        await bot.delete_message(chat_id=TEACHER_ID, message_id=forwarded_msg_id)
    except:
        pass
    
    del message_student_map[message_id]
    await callback_query.answer("✅ Baho muvaffaqiyatli qo'yildi!")

# Update show_group_statistics function to include more detailed stats
async def get_group_average(db, group):
    async with db.execute("""
        SELECT 
            ROUND(AVG(CASE WHEN g.grade IS NOT NULL THEN g.grade ELSE 0 END), 1) as avg_grade,
            COUNT(DISTINCT u.user_id) as total_students,
            COUNT(g.grade) as total_retellings
        FROM users u
        LEFT JOIN grades g ON u.user_id = g.user_id
        WHERE u.group_name = ?
    """, (group,)) as cursor:
        return await cursor.fetchone()

@dp.callback_query(lambda c: c.data.startswith('stats_'))
async def show_group_statistics(callback_query: CallbackQuery):
    if callback_query.from_user.id != TEACHER_ID:
        await callback_query.answer("Bu funksiya faqat o'qituvchi uchun!")
        return

    group = callback_query.data.split('_')[1]
    
    async with aiosqlite.connect("mydatabase.db") as db:
        # Get group average statistics
        group_stats = await get_group_average(db, group)
        
        # Get individual student statistics
        async with db.execute("""
            SELECT u.full_name,
                   COUNT(g.grade) as total_retellings,
                   ROUND(AVG(g.grade), 1) as avg_grade,
                   SUM(CASE WHEN g.grade = 5 THEN 1 ELSE 0 END) as grade_5,
                   SUM(CASE WHEN g.grade = 4 THEN 1 ELSE 0 END) as grade_4,
                   SUM(CASE WHEN g.grade = 3 THEN 1 ELSE 0 END) as grade_3,
                   SUM(CASE WHEN g.grade = 2 THEN 1 ELSE 0 END) as grade_2,
                   SUM(CASE WHEN g.grade = 1 THEN 1 ELSE 0 END) as grade_1
            FROM users u
            LEFT JOIN grades g ON u.user_id = g.user_id
            WHERE u.group_name = ?
            GROUP BY u.user_id
            ORDER BY avg_grade DESC, total_retellings DESC
        """, (group,)) as cursor:
            students = await cursor.fetchall()

    if not students:
        await callback_query.message.answer(f"❌ {group}-guruhda hali o'quvchilar yo'q.")
        return

    avg_grade, total_students, total_retellings = group_stats
    
    stats_message = (
        f"📊 {group}-guruh statistikasi:\n\n"
        f"👥 Jami o'quvchilar: {total_students} ta\n"
        f"📝 Jami topshirilgan retellinglar: {total_retellings} ta\n"
        f"⭐️ O'rtacha ball: {avg_grade}\n"
        f"{'─' * 30}\n\n"
    )
    
    for student in students:
        name, total, avg, grade5, grade4, grade3, grade2, grade1 = student
        grades_info = (
            f"👤 {name}\n"
            f"📊 O'rtacha ball: {avg or 0}\n"
            f"📝 Jami topshirgan: {total or 0} ta\n"
            f"5️⃣ - {grade5 or 0} ta\n"
            f"4️⃣ - {grade4 or 0} ta\n"
            f"3️⃣ - {grade3 or 0} ta\n"
            f"2️⃣ - {grade2 or 0} ta\n"
            f"1️⃣ - {grade1 or 0} ta\n"
            f"{'─' * 30}\n"
        )
        stats_message += grades_info

    # Send stats in chunks if too long
    if len(stats_message) > 4096:
        for i in range(0, len(stats_message), 4096):
            await callback_query.message.answer(stats_message[i:i+4096])
    else:
        await callback_query.message.answer(stats_message)
    
    await callback_query.answer()


def get_tashkent_time(utc_time=None):
    tz_tashkent = pytz.timezone('Asia/Tashkent')
    if utc_time is None:
        utc_time = datetime.now(pytz.UTC)
    return utc_time.astimezone(tz_tashkent)

def format_time_period(start_time, end_time):
    duration = end_time - start_time
    minutes = duration.seconds // 60
    seconds = duration.seconds % 60
    return f"{minutes:02d}:{seconds:02d}"

# Add monthly statistics function
async def get_monthly_statistics(db, group=None):
    current_time = get_tashkent_time()
    start_of_month = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    
    query = """
        SELECT 
            u.group_name,
            COUNT(DISTINCT u.user_id) as total_students,
            COUNT(g.id) as total_retellings,
            ROUND(AVG(g.grade), 1) as avg_grade,
            SUM(CASE WHEN g.grade = 5 THEN 1 ELSE 0 END) as grade_5,
            SUM(CASE WHEN g.grade = 4 THEN 1 ELSE 0 END) as grade_4,
            SUM(CASE WHEN g.grade = 3 THEN 1 ELSE 0 END) as grade_3,
            SUM(CASE WHEN g.grade = 2 THEN 1 ELSE 0 END) as grade_2,
            SUM(CASE WHEN g.grade = 1 THEN 1 ELSE 0 END) as grade_1
        FROM users u
        LEFT JOIN grades g ON u.user_id = g.user_id
        WHERE g.date >= ?
    """
    
    if group:
        query += " AND u.group_name = ?"
        params = (start_of_month.isoformat(), group)
    else:
        query += " GROUP BY u.group_name ORDER BY avg_grade DESC"
        params = (start_of_month.isoformat(),)
    
    async with db.execute(query, params) as cursor:
        return await cursor.fetchall()

# Add new command for monthly statistics
@dp.message(Command("monthly"))
async def show_monthly_stats(message: types.Message):
    if message.from_user.id != TEACHER_ID:
        await message.answer("Bu buyruq faqat o'qituvchi uchun!")
        return

    keyboard = InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(
                    text="📊 Umumiy statistika",
                    callback_data="monthly_all"
                )
            ],
            [
                InlineKeyboardButton(
                    text="👥 Guruh bo'yicha",
                    callback_data="monthly_by_group"
                )
            ]
        ]
    )

    await message.answer(
        "Oylik statistikani ko'rish uchun tanlang:",
        reply_markup=keyboard
    )

@dp.callback_query(lambda c: c.data.startswith('monthly_'))
async def process_monthly_stats(callback_query: CallbackQuery):
    if callback_query.from_user.id != TEACHER_ID:
        await callback_query.answer("Bu funksiya faqat o'qituvchi uchun!")
        return

    action = callback_query.data.split('_')[1]
    
    if action == "by_group":
        # Show group selection keyboard for monthly stats
        keyboard = InlineKeyboardMarkup(
            inline_keyboard=[
                [InlineKeyboardButton(text=group, callback_data=f"monthly_group_{group}")]
                for group in GROUPS
            ]
        )
        await callback_query.message.edit_text(
            "Guruhni tanlang:",
            reply_markup=keyboard
        )
    else:  # all groups
        async with aiosqlite.connect("mydatabase.db") as db:
            stats = await get_monthly_statistics(db)
            
        if not stats:
            await callback_query.message.edit_text("Bu oy uchun ma'lumotlar topilmadi.")
            return
            
        current_month = get_tashkent_time().strftime("%B %Y")
        message = f"📊 {current_month} oyi uchun statistika:\n\n"
        
        for stat in stats:
            group, students, retellings, avg, g5, g4, g3, g2, g1 = stat
            message += (
                f"👥 {group}-guruh:\n"
                f"📚 O'quvchilar: {students} ta\n"
                f"📝 Retellinglar: {retellings or 0} ta\n"
                f"⭐️ O'rtacha ball: {avg or 0}\n"
                f"5️⃣ - {g5 or 0} ta\n"
                f"4️⃣ - {g4 or 0} ta\n"
                f"3️⃣ - {g3 or 0} ta\n"
                f"2️⃣ - {g2 or 0} ta\n"
                f"1️⃣ - {g1 or 0} ta\n"
                f"{'─' * 30}\n"
            )
            
        await callback_query.message.edit_text(message)
    
    await callback_query.answer()

@dp.callback_query(lambda c: c.data.startswith('monthly_group_'))
async def show_group_monthly_stats(callback_query: CallbackQuery):
    if callback_query.from_user.id != TEACHER_ID:
        await callback_query.answer("Bu funksiya faqat o'qituvchi uchun!")
        return

    group = callback_query.data.split('_')[2]
    
    async with aiosqlite.connect("mydatabase.db") as db:
        # Get monthly group statistics
        stats = await get_monthly_statistics(db, group)
        
        # Get detailed student statistics for the month
        current_time = get_tashkent_time()
        start_of_month = current_time.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        async with db.execute("""
            SELECT 
                u.full_name,
                COUNT(g.id) as total_retellings,
                ROUND(AVG(g.grade), 1) as avg_grade,
                SUM(CASE WHEN g.grade = 5 THEN 1 ELSE 0 END) as grade_5,
                SUM(CASE WHEN g.grade = 4 THEN 1 ELSE 0 END) as grade_4,
                SUM(CASE WHEN g.grade = 3 THEN 1 ELSE 0 END) as grade_3,
                SUM(CASE WHEN g.grade = 2 THEN 1 ELSE 0 END) as grade_2,
                SUM(CASE WHEN g.grade = 1 THEN 1 ELSE 0 END) as grade_1
            FROM users u
            LEFT JOIN grades g ON u.user_id = g.user_id
            WHERE u.group_name = ? AND g.date >= ?
            GROUP BY u.user_id
            ORDER BY avg_grade DESC, total_retellings DESC
        """, (group, start_of_month.isoformat())) as cursor:
            students = await cursor.fetchall()

    if not stats and not students:
        await callback_query.message.edit_text(
            f"❌ {group}-guruh uchun bu oy ma'lumotlar topilmadi."
        )
        return

    current_month = current_time.strftime("%B %Y")
    message = f"📊 {group}-guruh, {current_month} oyi statistikasi:\n\n"

    if stats:
        _, students_count, retellings, avg, g5, g4, g3, g2, g1 = stats[0]
        message += (
            f"📚 Jami o'quvchilar: {students_count} ta\n"
            f"📝 Jami retellinglar: {retellings or 0} ta\n"
            f"⭐️ O'rtacha ball: {avg or 0}\n"
            f"5️⃣ - {g5 or 0} ta\n"
            f"4️⃣ - {g4 or 0} ta\n"
            f"3️⃣ - {g3 or 0} ta\n"
            f"2️⃣ - {g2 or 0} ta\n"
            f"1️⃣ - {g1 or 0} ta\n"
            f"{'─' * 30}\n\n"
            f"👤 O'quvchilar bo'yicha:\n\n"
        )

    for student in students:
        name, total, avg, g5, g4, g3, g2, g1 = student
        message += (
            f"📌 {name}\n"
            f"📊 O'rtacha: {avg or 0}\n"
            f"📝 Topshirgan: {total or 0} ta\n"
            f"5️⃣ - {g5 or 0} ta\n"
            f"4️⃣ - {g4 or 0} ta\n"
            f"3️⃣ - {g3 or 0} ta\n"
            f"2️⃣ - {g2 or 0} ta\n"
            f"1️⃣ - {g1 or 0} ta\n"
            f"{'─' * 30}\n"
        )

    # Send in chunks if too long
    if len(message) > 4096:
        for i in range(0, len(message), 4096):
            await callback_query.message.answer(message[i:i+4096])
        await callback_query.message.delete()
    else:
        await callback_query.message.edit_text(message)
    
    await callback_query.answer()
def get_current_utc():
    return datetime.now(pytz.UTC).strftime("%Y-%m-%d %H:%M:%S")

def get_current_tashkent():
    return get_tashkent_time().strftime("%Y-%m-%d %H:%M:%S")

# Add help command
@dp.message(Command("help"))
async def show_help(message: types.Message):
    current_time_utc = get_current_utc()
    current_time_tashkent = get_current_tashkent()
    
    if message.from_user.id == TEACHER_ID:
        help_text = (
            "🎓 O'qituvchi uchun buyruqlar:\n\n"
            "/start - Botni ishga tushirish va statistika ko'rish\n"
            "/monthly - Oylik statistikani ko'rish\n"
            "/help - Yordam xabarini ko'rish\n\n"
            "📊 Statistika:\n"
            "- Guruhlar bo'yicha statistika\n"
            "- Oylik statistika\n"
            "- O'quvchilar reytingi\n\n"
            "⭐️ Baholash:\n"
            "- Video reteling kelganda avtomatik ko'rsatiladi\n"
            "- 1 dan 5 gacha baho qo'yish mumkin\n\n"
            f"🕒 Joriy vaqt (UTC): {current_time_utc}\n"
            f"🕒 Joriy vaqt (Toshkent): {current_time_tashkent}"
        )
    else:
        help_text = (
            "🎓 O'quvchi uchun buyruqlar:\n\n"
            "/start - Botni ishga tushirish va ro'yxatdan o'tish\n"
            "/help - Yordam xabarini ko'rish\n\n"
            "📝 Reteling topshirish:\n"
            "1. Mavzu kiriting\n"
            "2. Video yuboring\n"
            "3. O'qituvchi bahosini kuting\n\n"
            "📊 Statistika:\n"
            "- Baho qo'yilganda avtomatik ko'rsatiladi\n\n"
            f"🕒 Joriy vaqt: {current_time_tashkent}"
        )
    
    # Log help command usage
    user_info = (
        f"User: {message.from_user.username or message.from_user.id}\n"
        f"Time (UTC): {current_time_utc}\n"
        f"Time (Tashkent): {current_time_tashkent}"
    )
    logging.info(f"Help command used by:\n{user_info}")
    
    await message.answer(help_text)

async def main():
    # Configure logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('bot.log'),
            logging.StreamHandler()
        ]
    )
    
    # Initialize logger
    logger = logging.getLogger("bot")
    
    # Log startup information
    current_time_utc = get_current_utc()
    current_time_tashkent = get_current_tashkent()
    
    startup_info = (
        "Bot starting up...\n"
        f"Current Date and Time (UTC): {current_time_utc}\n"
        f"Current Date and Time (Tashkent): {current_time_tashkent}\n"
        f"Current User's Login: {os.getlogin()}"
    )
    
    logger.info(startup_info)
    
    try:
        # Initialize database
        await init_db()
        logger.info("Database initialized successfully")
        
        # Start polling
        logger.info("Starting bot polling...")
        await dp.start_polling(bot)
        
    except Exception as e:
        logger.error(f"Error during bot startup: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logging.info("Bot stopped by user")
    except Exception as e:
        logging.error(f"Unexpected error: {e}", exc_info=True)
    finally:
        logging.info("Bot shutdown complete")