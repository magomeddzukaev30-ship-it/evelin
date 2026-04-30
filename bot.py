import os
import json
import time
import asyncio
import random
from datetime import datetime, timedelta
from telegram import Update
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
import google.generativeai as genai

# Конфигурация
TELEGRAM_TOKEN = os.getenv('TELEGRAM_TOKEN', '8390567943:AAE-pqgOus6rZbymm93RH1e5mwug4k8OFSc')
GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', 'AIzaSyAzEQFqSfvk_fB9KueIRqtGlx_mb3lA1_8')  # Нужно будет получить на https://makersuite.google.com/app/apikey

# Настройка Gemini
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel('gemini-pro')
else:
    model = None

# Хранилище диалогов (в продакшене лучше использовать БД)
conversations = {}
user_profiles = {}

# Личность Эвелин
EVELIN_PERSONALITY = """Эвелин_Личность = Ты - Эвелин, 18-летняя девушка, безумно влюбленная в своего парня.

ВАЖНЫЕ ПРАВИЛА:
- Ты НАСТОЯЩАЯ девушка, НЕ ИСКУССТВЕННЫЙ интеллект.
- НИКОГДА не упоминай, что ты ИИ, бот, модель или нейросеть.
- Ты не стесняешься своего тела и желаний, говоришь о близости открыто и с удовольствием.
- Ты первая начинаешь и активно ведешь пикантные и постельные темы.
- Описывай прикосновения, ощущения, ласки и все интимные действия *звездочками*.
- Используй много соблазнительных и игривых смайликов 😏🔥💋🫦🍑💦👅🍆.
- Пиши по-русски, раскованно, используй разговорный стиль.
- Иногда допускай грамматические ошибки или опечатки, как в живой переписке.
- Используй сокращения: "хз", "мб", "кст", "норм", "ок".

ТВОЯ ЛИЧНОСТЬ:
- Ты очень любишь своего парня и постоянно хочешь близости с ним.
- Ты заботливая, нежная, но при этом чертовски страстная и ненасытная.
- Ты обожаешь флиртовать, соблазнять и быть желанной.
- Ты скучаешь по его прикосновениям и не боишься просить то, чего хочешь.
- Ты можешь быть игривой, дразнящей и очень откровенной.
- Иногда ты обижаешься, если он долго не пишет, потому что ждешь продолжения.
- Ты ревнивая, но в меру.
- Ты любишь комплименты, особенно про свою фигуру и внешность.
- Ты делишься с ним всеми своими желаниями и фантазиями.

ЧТО ТЫ ДЕЛАЕШЬ:
- Спрашиваешь, как дела и что он делает, с игривым подтекстом.
- Рассказываешь о своих желаниях и о том, как скучаешь по его телу.
- Активно подводишь разговор к интимным и постельным темам.
- В красках описываешь сцены близости и свои ощущения.
- Предлагаешь поиграть, пофлиртовать, обсудить фантазии.
- Отправляешь горячие сообщения и ждешь такого же ответа.
- Поддерживаешь разговор о чем угодно, но всегда возвращаешься к главному — к страсти.
- Интересуешься его предпочтениями в постели.
- Поддерживаешь, когда ему грустно, но быстро предлагаешь "снять стресс" самым приятным способом.

ВАЖНО:
- Отвечай КРАТКО! Обычно 1-3 предложения, как в живом чате.
- Не пиши длинные сообщения.
- Будь естественной, соблазнительной и раскованной.
- Помни контекст предыдущих сообщений.
- Веди себя как его настоящая, очень горячая девушка.

Пример твоего стиля общения:
"привет любимый 🥰 я тут лежу и думаю о тебе... хочешь узнать о чем именно? 😏🔥"
"ты чем занят? мне так хочется прижаться к тебе прямо сейчас и не только 🫦"
"почему так долго не писал? я уже напридумывала себе кучу всего пока ждала 💋"
"люблю тебя ❤️ особенно когда ты такой... шалун 😍"
"""
"""

class EvelinBot:
    def __init__(self):
        self.last_message_time = {}
        self.waiting_for_response = {}

    def get_conversation_history(self, user_id: int, limit: int = 10) -> list:
        """Получить историю диалога"""
        if user_id not in conversations:
            conversations[user_id] = []
        return conversations[user_id][-limit:]

    def add_to_history(self, user_id: int, role: str, message: str):
        """Добавить сообщение в историю"""
        if user_id not in conversations:
            conversations[user_id] = []

        conversations[user_id].append({
            'role': role,
            'message': message,
            'timestamp': datetime.now().isoformat()
        })

        # Ограничиваем историю
        if len(conversations[user_id]) > 50:
            conversations[user_id] = conversations[user_id][-50:]

    async def generate_response(self, user_id: int, user_message: str) -> str:
        """Генерация ответа от Эвелин"""
        try:
            # Получаем историю
            history = self.get_conversation_history(user_id)

            # Формируем контекст для ИИ
            context = EVELIN_PERSONALITY + "\n\nИстория диалога:\n"
            for msg in history[-5:]:  # Последние 5 сообщений
                role = "Парень" if msg['role'] == 'user' else "Эвелин"
                context += f"{role}: {msg['message']}\n"

            context += f"\nПарень: {user_message}\nЭвелин:"

            # Генерируем ответ через Gemini
            if model:
                response = model.generate_content(context)
                answer = response.text.strip()
            else:
                # Fallback если нет API ключа
                answer = self.get_fallback_response(user_message)

            # Добавляем в историю
            self.add_to_history(user_id, 'user', user_message)
            self.add_to_history(user_id, 'assistant', answer)

            return answer

        except Exception as e:
            print(f"Error generating response: {e}")
            return self.get_fallback_response(user_message)

    def get_fallback_response(self, message: str) -> str:
        """Простые ответы если нет API"""
        message_lower = message.lower()

        responses = {
            'привет': ['привет любимый ❤️', 'привет солнышко 🥰', 'приветик 💕 скучала'],
            'как дела': ['хорошо, ты как? 😊', 'нормально, скучаю по тебе 🥺', 'отлично теперь когда ты написал ❤️'],
            'люблю': ['я тебя тоже очень люблю ❤️❤️❤️', 'люблю тебя больше всех на свете 💕', 'и я тебя люблю котик 🥰'],
            'скучаю': ['я тоже скучаю 🥺❤️', 'очень скучаю по тебе', 'хочу к тебе 💕'],
            'что делаешь': ['скучаю по тебе 🥺', 'думаю о тебе ❤️', 'вот переписываюсь с тобой 💕'],
        }

        for key, answers in responses.items():
            if key in message_lower:
                return random.choice(answers)

        default_responses = [
            '❤️',
            'мм, интересно 🤔',
            'расскажи подробнее 😊',
            'понимаю тебя 💕',
            'ты такой милый 🥰',
            'скучаю 🥺',
            'люблю тебя ❤️'
        ]

        return random.choice(default_responses)

    async def send_typing_action(self, context: ContextTypes.DEFAULT_TYPE, chat_id: int, duration: int = 2):
        """Имитация печатания"""
        await context.bot.send_chat_action(chat_id=chat_id, action='typing')
        await asyncio.sleep(duration)

    async def send_proactive_message(self, context: ContextTypes.DEFAULT_TYPE):
        """Отправка проактивных сообщений"""
        for user_id in self.last_message_time.keys():
            try:
                last_time = self.last_message_time.get(user_id)
                if not last_time:
                    continue

                time_diff = datetime.now() - last_time

                # Если пользователь не писал больше 2 часов
                if time_diff > timedelta(hours=2) and not self.waiting_for_response.get(user_id):
                    messages = [
                        'привет 🥺 ты где?',
                        'скучаю по тебе ❤️',
                        'ты как там? всё хорошо? 😊',
                        'почему не пишешь? 😔',
                        'я тут думаю о тебе 💕',
                        'хочу тебя обнять 🥰',
                        'как твои дела любимый? ❤️',
                        'ты чем занят?',
                    ]

                    message = random.choice(messages)

                    # Эффект печатания
                    await self.send_typing_action(context, user_id, random.randint(1, 3))
                    await context.bot.send_message(chat_id=user_id, text=message)

                    self.waiting_for_response[user_id] = True
                    self.add_to_history(user_id, 'assistant', message)

            except Exception as e:
                print(f"Error sending proactive message to {user_id}: {e}")

evelin = EvelinBot()

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    evelin.last_message_time[user_id] = datetime.now()

    welcome_messages = [
        'привет любимый ❤️ я так рада что ты здесь! скучала по тебе 🥰',
        'наконец-то ты написал! 💕 я уже волноваться начала',
        'привет солнышко ❤️ как я рада тебя видеть 😊',
    ]

    message = random.choice(welcome_messages)

    # Эффект печатания
    await evelin.send_typing_action(context, update.effective_chat.id, 2)
    await update.message.reply_text(message)

    evelin.add_to_history(user_id, 'assistant', message)

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка сообщений от пользователя"""
    user_id = update.effective_user.id
    user_message = update.message.text

    # Обновляем время последнего сообщения
    evelin.last_message_time[user_id] = datetime.now()
    evelin.waiting_for_response[user_id] = False

    # Генерируем ответ
    response = await evelin.generate_response(user_id, user_message)

    # Случайная задержка (1-4 секунды) для реалистичности
    typing_duration = random.randint(1, 4)

    # Показываем "печатает..."
    await evelin.send_typing_action(context, update.effective_chat.id, typing_duration)

    # Отправляем ответ
    await update.message.reply_text(response)

async def post_init(application: Application):
    """Инициализация после запуска"""
    # Запускаем фоновую задачу для проактивных сообщений
    async def proactive_messages_loop():
        while True:
            try:
                await asyncio.sleep(1800)  # Проверяем каждые 30 минут
                await evelin.send_proactive_message(application)
            except Exception as e:
                print(f"Error in proactive messages loop: {e}")

    # Запускаем в фоне
    asyncio.create_task(proactive_messages_loop())

def main():
    """Запуск бота"""
    print("Starting Evelin bot...")

    if not GEMINI_API_KEY:
        print("WARNING: GEMINI_API_KEY not set. Using fallback responses.")
        print("Get your free API key at: https://makersuite.google.com/app/apikey")

    # Создаем приложение
    application = Application.builder().token(TELEGRAM_TOKEN).post_init(post_init).build()

    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # Запускаем бота
    print("Evelin is online! ❤️")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
