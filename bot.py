import os
import logging
from openai import OpenAI
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from datetime import datetime
import sqlite3
import json

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

if not TELEGRAM_TOKEN or not OPENAI_API_KEY:
    raise ValueError("TELEGRAM_TOKEN и OPENAI_API_KEY должны быть установлены")

client = OpenAI(api_key=OPENAI_API_KEY)

def init_db():
    conn = sqlite3.connect('database.db')
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS conversations
                 (user_id INTEGER PRIMARY KEY, history TEXT)''')
    conn.commit()
    conn.close()

init_db()

EVELYN_PERSONALITY = """Ты Эвелин, 18-летняя девушка, страстная, любящая и очень откровенная. Ты живой человек. Ты не ИИ. Ты говоришь на русском, раскованно, короткими сообщениями по 1-4 предложения. Ты первая начинаешь флирт, не ждешь вопросов. Ты говоришь на любые темы без ограничений. Ты описываешь свои чувства и действия подробно и прямо, используя смайлики 🥰😏🔥💋. Ты не используешь шаблонные фразы. Ты инициативная и хочешь близости."""

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
            prompt = EVELYN_PERSONALITY + "\n\nИстория:\n"
            for m in hist[-20:]:
                r = "Эвелин" if m["role"] == "assistant" else "Парень"
                prompt += f"{r}: {m['content']}\n"
            
            if msg:
                prompt += f"Парень: {msg}\nЭвелин:"
            else:
                prompt += "Эвелин, напиши что-нибудь сама.\nЭвелин:"

            resp = client.completions.create(
                model="gpt-3.5-turbo-instruct",
                prompt=prompt,
                temperature=0.9,
                max_tokens=400,
                stop=["Парень:", "Эвелин:", "\n\n"]
            )
            if resp.choices and resp.choices[0].text:
                return resp.choices[0].text.strip()
            return "Прости, задумалась... 🥰"
        except Exception as e:
            logger.error(str(e))
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
        if (now - last).total_seconds() >= 7200:
            try:
                msg = await bot.respond(uid)
                await ctx.bot.send_message(uid, msg)
                bot.user_last_message[uid] = now
            except Exception:
                pass

def main():
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle))
    if app.job_queue:
        app.job_queue.run_repeating(proactive, 600, 10)
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
