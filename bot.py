import asyncio
import os
import sqlite3
from datetime import date

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import CommandStart
from aiogram.utils.keyboard import ReplyKeyboardBuilder, InlineKeyboardBuilder

from dotenv import load_dotenv
from groq import Client

# =================
# LOAD TOKENS
# =================
load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

client = Client(api_key=GROQ_API_KEY)

# =================
# DATABASE
# =================
conn = sqlite3.connect("history_users.db")
cursor = conn.cursor()

cursor.execute("""
CREATE TABLE IF NOT EXISTS users(
id INTEGER PRIMARY KEY,
score INTEGER DEFAULT 0,
xp INTEGER DEFAULT 0
)
""")
conn.commit()

# =================
# MEMORY
# =================
user_modes = {}
user_history = {}
quiz_answers = {}
quest_stage = {}
exam_mode = {}

# =================
# ACHIEVEMENTS
# =================
achievements = {
    10: "🎖 Новичок истории",
    50: "🏺 Знаток ВКЛ",
    100: "👑 Магистр истории"
}

# =================
# PROMPT
# =================
SYSTEM_PROMPT = """
Ты AI учитель истории Беларуси.
Отвечай только на вопросы по истории Беларуси.
Объясняй понятно для подростков.
"""

# =================
# UTILS
# =================
def get_level(xp):
    return xp // 20 + 1

def get_user(uid):
    cursor.execute("SELECT score,xp FROM users WHERE id=?", (uid,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users(id,score,xp) VALUES(?,?,?)", (uid,0,0))
        conn.commit()
        return (0,0)
    return user

def add_score(uid):
    cursor.execute("UPDATE users SET score=score+1 WHERE id=?", (uid,))
    conn.commit()

def add_xp(uid,xp):
    cursor.execute("UPDATE users SET xp=xp+? WHERE id=?", (xp,uid))
    conn.commit()

def get_achievement(xp):
    result = None
    for req, name in achievements.items():
        if xp >= req:
            result = name
    return result

async def send_long_message(message,text):
    limit = 3900
    parts = [text[i:i+limit] for i in range(0,len(text),limit)]
    for p in parts:
        await message.answer(p)

# =================
# AI
# =================
async def groq_chat(messages):
    try:
        response = client.chat.completions.create(
            model="openai/gpt-oss-120b",
            messages=messages,
            temperature=0.7,
            max_tokens=500
        )
        return response.choices[0].message.content
    except Exception as e:
        return f"AI ошибка: {e}"

# =================
# MENU
# =================
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📚 Спросить ИИ")
    kb.button(text="📖 Объясни тему")
    kb.button(text="🎮 Викторина")
    kb.button(text="🔥 Викторина дня")
    kb.button(text="🎓 AI Экзамен")
    kb.button(text="🧩 Исторический квест")
    kb.button(text="📅 Событие дня")
    kb.button(text="👤 Профиль")
    kb.button(text="🏆 Лидеры")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# =================
# START
# =================
@dp.message(CommandStart())
async def start(message: Message):
    get_user(message.from_user.id)
    await message.answer(
        "🇧🇾 AI бот для изучения истории Беларуси",
        reply_markup=main_menu()
    )

# =================
# PROFILE
# =================
@dp.message(F.text=="👤 Профиль")
async def profile(message: Message):
    score,xp = get_user(message.from_user.id)
    level = get_level(xp)
    ach = get_achievement(xp)
    text=f"""
👤 Профиль
🏆 Баллы: {score}
⭐ XP: {xp}
🎖 Уровень: {level}
"""
    if ach:
        text += f"\n🏅 Достижение: {ach}"
    await message.answer(text)

# =================
# AI CHAT
# =================
@dp.message(F.text=="📚 Спросить ИИ")
async def ai_mode(message: Message):
    user_modes[message.from_user.id] = "ai"
    await message.answer("Задай вопрос по истории Беларуси")

# =================
# EXPLAIN MODE
# =================
@dp.message(F.text=="📖 Объясни тему")
async def explain_mode(message: Message):
    user_modes[message.from_user.id] = "explain"
    await message.answer("Напиши тему")

# =================
# DAILY QUIZ
# =================
@dp.message(F.text=="🔥 Викторина дня")
async def daily_quiz(message: Message):
    prompt="Создай один вопрос викторины по истории Беларуси."
    answer = await groq_chat([{"role":"user","content":prompt}])
    await send_long_message(message,answer)

# =================
# QUIZ
# =================
@dp.message(F.text=="🎮 Викторина")
async def quiz(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Лёгкий",callback_data="quiz_easy")
    kb.button(text="Средний",callback_data="quiz_medium")
    kb.button(text="Сложный",callback_data="quiz_hard")
    kb.adjust(1)
    await message.answer("Выбери уровень",reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("quiz_"))
async def quiz_question(callback: CallbackQuery):
    level = callback.data.split("_")[1]
    prompt=f"Создай {level} вопрос по истории Беларуси.\nФормат:\nВопрос\nA)\nB)\nC)\nD)\nПравильный ответ: A"
    answer = await groq_chat([{"role":"user","content":prompt}])
    correct = "A"
    for line in answer.split("\n"):
        if "Правильный" in line:
            correct = line[-1]
    quiz_answers[callback.from_user.id] = correct
    kb = InlineKeyboardBuilder()
    kb.button(text="A",callback_data="ans_A")
    kb.button(text="B",callback_data="ans_B")
    kb.button(text="C",callback_data="ans_C")
    kb.button(text="D",callback_data="ans_D")
    kb.adjust(4)
    await callback.message.answer(answer,reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ans_"))
async def quiz_answer(callback: CallbackQuery):
    uid = callback.from_user.id
    ans = callback.data.split("_")[1]
    correct = quiz_answers.get(uid)
    if ans == correct:
        add_score(uid)
        add_xp(uid,5)
        await callback.message.answer("✅ Верно")
    else:
        await callback.message.answer(f"❌ Ответ: {correct}")

# =================
# EXAM
# =================
@dp.message(F.text=="🎓 AI Экзамен")
async def exam(message: Message):
    exam_mode[message.from_user.id] = True
    prompt="Задай сложный экзаменационный вопрос по истории Беларуси"
    answer = await groq_chat([{"role":"user","content":prompt}])
    await send_long_message(message,answer)

# =================
# EVENT
# =================
@dp.message(F.text=="📅 Событие дня")
async def event(message: Message):
    today = date.today().strftime("%d %B")
    prompt = f"Что произошло {today} в истории Беларуси?"
    answer = await groq_chat([{"role":"user","content":prompt}])
    await send_long_message(message,answer)

# =================
# LEADERS
# =================
@dp.message(F.text=="🏆 Лидеры")
async def leaders(message: Message):
    cursor.execute("SELECT score FROM users ORDER BY score DESC LIMIT 10")
    rows = cursor.fetchall()
    text="🏆 Лидеры\n\n"
    for i,row in enumerate(rows):
        text += f"{i+1}. {row[0]} баллов\n"
    await message.answer(text)

# =================
# QUEST
# =================
quest=[
    ("Ты в Полоцке XI века. Кто был князем?", "всеслав"),
    ("Назови первого белорусского печатника", "скорина"),
    ("Столица ВКЛ?", "вильн"),
    ("Кто возглавил восстание 1863?", "калинов"),
    ("Как называется парламент Беларуси?", "национ"),
    ("Назови Мирский замок", "мир")
]

@dp.message(F.text=="🧩 Исторический квест")
async def quest_start(message: Message):
    quest_stage[message.from_user.id] = 0
    await message.answer(quest[0][0])

# =================
# MAIN HANDLER
# =================
@dp.message()
async def handle(message: Message):
    uid = message.from_user.id

    # QUEST
    if uid in quest_stage:
        stage = quest_stage[uid]
        if quest[stage][1] in message.text.lower():
            add_xp(uid,10)
            stage += 1
            if stage >= len(quest):
                await message.answer("🎉 Квест пройден")
                quest_stage.pop(uid)
                return
            quest_stage[uid] = stage
            await message.answer("✅ Верно\n" + quest[stage][0])
        else:
            await message.answer("❌ Попробуй ещё")
        return

    # EXAM
    if exam_mode.get(uid):
        prompt = f"Проверь ответ ученика:\n{message.text}\nОцени и объясни."
        answer = await groq_chat([{"role":"user","content":prompt}])
        exam_mode.pop(uid)
        await send_long_message(message,answer)
        return

    # EXPLAIN
    if user_modes.get(uid) == "explain":
        prompt = f"Объясни тему истории Беларуси:\n{message.text}\nПросто для школьника."
        answer = await groq_chat([{"role":"user","content":prompt}])
        user_modes.pop(uid)
        await send_long_message(message,answer)
        return

    # AI CHAT
    if user_modes.get(uid) == "ai":
        history = user_history.setdefault(uid,[])
        history.append({"role":"user","content":message.text})
        messages = [{"role":"system","content":SYSTEM_PROMPT}] + history[-6:]
        answer = await groq_chat(messages)
        history.append({"role":"assistant","content":answer})
        await send_long_message(message,answer)
        return

# =================
# RUN
# =================
async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__=="__main__":
    asyncio.run(main())
