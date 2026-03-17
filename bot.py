import os
from aiogram import Bot, Dispatcher
from aiogram.types import Update
from aiogram.dispatcher.webhook.server import WebhookRequestHandler
from aiogram.dispatcher.webhook import get_new_configured_app
from groq import GroqClient
from fastapi import FastAPI, Request

BOT_TOKEN = os.getenv("BOT_TOKEN")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# Пример команды /start
@dp.message()
async def start_handler(message):
    await message.answer("Привет! Я бот по истории Беларуси.")

# Настройка Groq
client = GroqClient(api_key=GROQ_API_KEY)

# FastAPI приложение для Render
app = FastAPI()
asgi_app = get_new_configured_app(dp, bot=bot, path="/webhook")
app.mount("/", asgi_app)

# =========================
# ПАМЯТЬ
# =========================
user_scores = {}
user_xp = {}
quiz_answers = {}
user_modes = {}
user_history = {}
quest_stage = {}

# =========================
# SYSTEM PROMPT
# =========================
SYSTEM_PROMPT = """
Ты AI-учитель истории Беларуси.
Любые вопросы, не связанные с Историей Беларуси отклоняй.(Исключение: пункты меню)
Отвечай только на вопросы про историю Беларуси.
Объясняй понятно для подростков.
Отвечай кратко и интересно.
Ищи инфомрацию в следующих источниках:
https://ru.wikipedia.org/wiki/%D0%98%D1%81%D1%82%D0%BE%D1%80%D0%B8%D1%8F_%D0%91%D0%B5%D0%BB%D0%B0%D1%80%D1%83%D1%81%D0%B8?
"""

# =========================
# LEVEL SYSTEM
# =========================
def get_level(xp):
    return xp // 10 + 1

# =========================
# MAIN MENU
# =========================
def main_menu():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📚 Спросить ИИ")
    kb.button(text="🎮 Викторина")
    kb.button(text="🧩 Исторический квест")
    kb.button(text="🎓 Подготовка к экзамену")
    kb.button(text="🗺 Карта Беларуси")
    kb.button(text="📅 Событие дня")
    kb.button(text="🏆 Лидеры")
    kb.button(text="📊 Мой счёт")
    kb.button(text="🏅 Мой уровень")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)

# =========================
# AI CHAT через актуальный SDK
# =========================
async def groq_chat_sdk(messages):
    """
    messages = [{"role": "system/user/assistant", "content": "..."}]
    """
    response = client.chat.completions.create(
        model="openai/gpt-oss-120b",
        messages=messages
    )
    return response.choices[0].message.content

# =========================
# START
# =========================
@dp.message(CommandStart())
async def start(message: Message):
    uid = message.from_user.id
    user_scores.setdefault(uid,0)
    user_xp.setdefault(uid,0)
    user_history.setdefault(uid,[])
    await message.answer(
        "🇧🇾 AI бот для изучения истории Беларуси\n\nВыбери режим:",
        reply_markup=main_menu()
    )

# =========================
# AI MODE
# =========================
@dp.message(F.text == "📚 Спросить ИИ")
async def ai_mode(message: Message):
    user_modes[message.from_user.id] = "ai"
    await message.answer("Задай любой вопрос по истории Беларуси.")

@dp.message()
async def ai_chat(message: Message):
    uid = message.from_user.id
    if user_modes.get(uid,"ai") != "ai":
        return
    history = user_history.setdefault(uid, [])
    history.append({"role":"user","content":message.text})
    messages = [{"role":"system","content":SYSTEM_PROMPT}] + history[-6:]
    try:
        answer = await groq_chat_sdk(messages)
    except Exception as e:
        answer = f"Ошибка AI: {e}"
    history.append({"role":"assistant","content":answer})
    await message.answer(answer)

# =========================
# ВИКТОРИНА
# =========================
@dp.message(F.text == "🎮 Викторина")
async def quiz(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Лёгкий", callback_data="quiz_easy")
    kb.button(text="Средний", callback_data="quiz_medium")
    kb.button(text="Сложный", callback_data="quiz_hard")
    kb.adjust(1)
    await message.answer("Выбери уровень:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("quiz_"))
async def quiz_question(callback: CallbackQuery):
    level = callback.data.split("_")[1]
    prompt = f"""
Создай {level} вопрос викторины по истории Беларуси.

Формат:
Вопрос
A)
B)
C)
D)

Правильный ответ: A
"""
    answer = await groq_chat_sdk([{"role":"user","content":prompt}])
    correct = None
    for line in answer.split("\n"):
        if "Правильный ответ" in line:
            correct = line.strip()[-1]
    quiz_answers[callback.from_user.id] = correct

    kb = InlineKeyboardBuilder()
    kb.button(text="A", callback_data="ans_A")
    kb.button(text="B", callback_data="ans_B")
    kb.button(text="C", callback_data="ans_C")
    kb.button(text="D", callback_data="ans_D")
    kb.adjust(4)
    await callback.message.answer(answer, reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("ans_"))
async def quiz_answer(callback: CallbackQuery):
    uid = callback.from_user.id
    user_answer = callback.data.split("_")[1]
    correct = quiz_answers.get(uid)
    if user_answer == correct:
        user_scores[uid]+=1
        user_xp[uid]+=3
        await callback.message.answer("✅ Верно! +1 балл")
    else:
        await callback.message.answer(f"❌ Неверно. Ответ: {correct}")

# =========================
# СЧЁТ
# =========================
@dp.message(F.text == "📊 Мой счёт")
async def score(message: Message):
    score = user_scores.get(message.from_user.id,0)
    await message.answer(f"Твой счёт: {score}")

# =========================
# УРОВЕНЬ
# =========================
@dp.message(F.text == "🏅 Мой уровень")
async def level(message: Message):
    xp = user_xp.get(message.from_user.id,0)
    lvl = get_level(xp)
    await message.answer(f"🏅 Уровень: {lvl}\n⭐ Опыт: {xp}")

# =========================
# ЛИДЕРЫ
# =========================
@dp.message(F.text == "🏆 Лидеры")
async def leaders(message: Message):
    top = sorted(user_scores.items(), key=lambda x:x[1], reverse=True)
    text = "🏆 Таблица лидеров\n\n"
    for i,(user,score) in enumerate(top[:10]):
        text += f"{i+1}. {score} баллов\n"
    await message.answer(text)

# =========================
# СОБЫТИЕ ДНЯ
# =========================
@dp.message(F.text == "📅 Событие дня")
async def day_event(message: Message):
    today = date.today().strftime("%d %B")
    prompt = f"Какое событие произошло {today} в истории Беларуси?"
    answer = await groq_chat_sdk([{"role":"user","content":prompt}])
    await message.answer(answer)

# =========================
# КАРТА
# =========================
@dp.message(F.text == "🗺 Карта Беларуси")
async def map_menu(message: Message):
    kb = InlineKeyboardBuilder()
    kb.button(text="Минск", callback_data="city_minsk")
    kb.button(text="Полоцк", callback_data="city_polotsk")
    kb.button(text="Гродно", callback_data="city_grodno")
    kb.button(text="Брест", callback_data="city_brest")
    kb.adjust(2)
    await message.answer("Выбери город:", reply_markup=kb.as_markup())

@dp.callback_query(F.data.startswith("city_"))
async def city_info(callback: CallbackQuery):
    city = callback.data.split("_")[1]
    prompt = f"Расскажи кратко историю города {city} в Беларуси."
    answer = await groq_chat_sdk([{"role":"user","content":prompt}])
    await callback.message.answer(answer)

# =========================
# ИСТОРИЧЕСКИЙ КВЕСТ
# =========================
@dp.message(F.text == "🧩 Исторический квест")
async def start_quest(message: Message):
    quest_stage[message.from_user.id] = 1
    await message.answer(
        "🧩 Квест начался!\nТы оказался в Полоцке XI века.\nКто был князем Полоцка?"
    )

@dp.message()
async def quest_answer(message: Message):
    uid = message.from_user.id
    stage = quest_stage.get(uid)
    if stage == 1:
        if "всеслав" in message.text.lower():
            quest_stage[uid] = 2
            user_xp[uid] += 5
            await message.answer(
                "Верно! Это Всеслав Чародей.\nСледующая задача:\nНазови первого белорусского печатника."
            )
        else:
            await message.answer("Попробуй ещё!")
    elif stage == 2:
        if "скорина" in message.text.lower():
            quest_stage[uid] = 3
            user_xp[uid] += 5
            await message.answer("Правильно! Это Франциск Скорина.\nКвест завершён 🎉")
        else:
            await message.answer("Попробуй ещё.")

# =========================
# RUN
# =========================
async def main():
    print("Bot started")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())