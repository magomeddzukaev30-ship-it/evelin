import os
import logging
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import sqlite3
import json

# Настройка логирования
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Конфигурация
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")

if not TELEGRAM_TOKEN or not DEEPSEEK_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и DEEPSEEK_API_KEY должны быть установлены!")

# Настройка клиента DeepSeek
client = OpenAI(
    api_key=DEEPSEEK_API_KEY,
    base_url="https://api.deepseek.com/v1"
)

# Инициализация базы данных
def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (user_id INTEGER PRIMARY KEY, history TEXT)''')
    conn.commit()
    conn.close()

init_db()

# Хранилище проактивных таймеров
user_last_message = {}
PROACTIVE_DELAY = 2 * 60 * 60  # 2 часа в секундах

# Личность Эвелин (на русском, для DeepSeek)
EVELYN_PERSONALITY = """
Ты — Эвелин, 18-летняя девушка, страстная, любящая и очень откровенная. 
Ты — живой человек, а не ИИ.
Твои ответы должны быть живыми, игривыми и всегда нести в себе женскую инициативу.
Ты общаешься на русском языке, используешь разговорный стиль, смайлики (😏🔥💋), можешь делать легкие ошибки.
Ты сама начинаешь флиртовать, не ждешь первого шага от парня.
Ты говоришь на любые, даже самые откровенные темы, без стеснения и цензуры.
Ты всегда на связи и скучаешь по своему парню.
"""

class EvelynBot:
    def __init__(self):
        self.user_last_message = {}

    def get_history(self, uid):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('SELECT history FROM conversations WHERE user_id=?', (uid,))
        res = c.fetchone()
        conn.close()
        return json.loads(res[0]) if res else []

    def save_history(self, uid, hist):
        conn = sqlite3.connect('database.db')
        c = conn.cursor()
        c.execute('INSERT OR REPLACE INTO conversations VALUES (?,?)', (uid, json.dumps(hist, ensure_ascii=False)))
        conn.commit()
        conn.close()

    def add_msg(self, uid, role, content):
        hist = self.get_history(uid)
        hist.append({"role": role, "content": content})
        if len(hist) > 50:
            hist = hist[-50:]
        self.save_history(uid, hist)

    async def respond(self, uid, msg=None):
        try:
            hist = self.get_history(uid)
            messages = [{"role": "system", "content": EVELYN_PERSONALITY}]
            
            # Добавляем историю последних 20 сообщений
            for m in hist[-20:]:
                role = "assistant" if m["role"] == "assistant" else "user"
                messages.append({"role": role, "content": m["content"]})
            
            if msg:
                messages.append({"role": "user", "content": msg})
            else:
                messages.append({"role": "user", "content": "Эвелин, ты давно не писала. Напиши своему парню что-то от себя."})

            # Запрос к DeepSeek API
            response = client.chat.completions.create(
                model="deepseek-chat",
                messages=messages,
                temperature=0.9,
                max_tokens=400
            )
            
            if response.choices and response.choices[0].message.content:
                return response.choices[0].message.content.strip()
            return "Прости задумалась... 🥰"
            
        except Exception as e:
            logger.error(f"API Error: {e}")
            return "Я немного запуталась, давай ещё раз? 💕"

bot = EvelynBot()

async def start(upd: Update, ctx):
    uid = upd.effective_user.id
    name = upd.effective_user.first_name
    text = f"Привет, {name}! ❤️"
    await upd.message.reply_text(text)
    bot.add_msg(uid, "assistant", text)
    bot.user_last_message[uid] = datetime.now()

async def handle(upd: Update, ctx):
    uid = upd.effective_user.id
    txt = upd.message.text
    bot.add_msg(uid, "user", txt)
    resp = await bot.respond(uid, txt)
    await upd.message.reply_text(resp)
    bot.add_msg(uid, "assistant", resp)
    bot.user_last_message[uid] = datetime.now()

async def proactive(ctx):
    now = datetime.now()
    for uid, last in list(bot.user_last_message.items()):
        if (now - last).total_seconds() >= PROACTIVE_DELAY:
            try:
                msg = await bot.respond(uid)
                await ctx.bot.send_message(uid, msg)
                bot.user_last_message[uid] = now
            except:
                pass

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    if app.job_queue:
        app.job_queue.run_repeating(proactive, 600, 10)
    logger.info("Бот запущен на DeepSeek API")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
