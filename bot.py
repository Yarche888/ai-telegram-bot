import os
import time
from threading import Thread
import telebot
from flask import Flask
import google.generativeai as genai

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USER_ID = int(os.environ.get("USER_ID", 0))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

# Инициализируем официальный SDK Google Gemini
genai.configure(api_key=GEMINI_KEY)

# Настраиваем модель
model = genai.GenerativeModel('gemini-3.8-flash')

bot = telebot.TeleBot(BOT_TOKEN)

def check_access(message):
    return message.from_user.id == USER_ID

def ask_gemini(prompt_text):
    """Запрос через официальный SDK Google"""
    try:
        response = model.generate_content(prompt_text)
        if response and response.text:
            return response.text
        else:
            return "⚠️ Модель вернула пустой ответ."
    except Exception as e:
        return f"❌ Ошибка при обращении к Gemini: {e}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    bot.reply_to(message, "Привет! Бот на официальном SDK Gemini запущен и готов к работе.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    
    answer = ask_gemini(message.text)
    bot.reply_to(message, answer)

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
