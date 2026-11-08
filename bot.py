import os
import time
from threading import Thread
import telebot
from flask import Flask
from google import genai
from google.genai.errors import APIError

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USER_ID = int(os.environ.get("USER_ID", 0))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Инициализируем новый официальный клиент Google GenAI
client = genai.Client(api_key=GEMINI_KEY)

# 🔍 Проверяем доступные модели для твоего ключа (выведется в логи Render)
print("🔍 Проверяем доступные модели для твоего ключа...")
try:
    for m in client.models.list():
        print(f"Доступна модель: {m.name}")
except Exception as e:
    print(f"⚠️ Ошибка при получении списка моделей: {e}")

bot = telebot.TeleBot(BOT_TOKEN)

def check_access(message):
    return message.from_user.id == USER_ID

def ask_gemini(prompt_text, retries=3, delay=5):
    """Запрос через актуальный клиент Google GenAI с автоповтором при перегрузке (429)"""
    for attempt in range(retries):
        try:
            response = client.models.generate_content(
                model='models/gemini-2.5-flash',  # <-- указали полное имя из логов
                contents=prompt_text,
            )
            if response and response.text:
                return response.text
            else:
                return "⚠️ Модель вернула пустой ответ."
        except APIError as e:
            # Обрабатываем ошибки API, включая лимиты
            if "429" in str(e) or "ResourceExhausted" in str(e):
                if attempt < retries - 1:
                    print(f"⚠️ Превышен лимит запросов (429). Ждем {delay} сек. (попытка {attempt + 2}/{retries})...")
                    time.sleep(delay)
                    continue
                else:
                    return "❌ Слишком много запросов. Лимит исчерпан, попробуй чуть позже."
            else:
                return f"❌ Ошибка API Gemini: {e}"
        except Exception as e:
            return f"❌ Ошибка при обращении к Gemini: {e}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    bot.reply_to(message, "Привет! Бот на новом клиенте Google GenAI запущен и готов к работе.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    
    ai_response = ask_gemini(message.text)
    bot.reply_to(message, ai_response)

# Настройка Flask для Render
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    print("⏳ Ожидание завершения предыдущих сессий...")
    time.sleep(3)

    print("🔄 Запуск ручного пуллинга бота...")
    bot.remove_webhook()

    # Запускаем Flask в отдельном потоке
    t_flask = Thread(target=run_flask)
    t_flask.daemon = True
    t_flask.start()

    offset = 0
    while True:
        try:
            updates = bot.get_updates(offset=offset, timeout=20)
            for update in updates:
                offset = update.update_id + 1
                bot.process_new_updates([update])
        except Exception as e:
            print(f"⚠️ Ошибка пуллинга: {e}")
            time.sleep(3)
