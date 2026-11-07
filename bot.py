import os
import time
from threading import Thread
import telebot
import requests
from bs4 import BeautifulSoup
from flask import Flask

# Загружаем переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USER_ID = int(os.environ.get("USER_ID", 0))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

bot = telebot.TeleBot(BOT_TOKEN)

def check_access(message):
    return message.from_user.id == USER_ID

def ask_gemini(prompt_text):
    """Запрос к модели с автоматическим повтором при ошибке 503"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    # Делаем до 3 попыток при временных ошибках
    for attempt in range(3):
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code == 200:
                data = response.json()
                try:
                    return data["candidates"][0]["content"]["parts"][0]["text"]
                except Exception:
                    return "Получен странный ответ от модели."
            elif response.status_code == 503:
                # Если сервер перегружен, ждем 3 секунды и пробуем снова
                time.sleep(3)
                continue
            else:
                return f"Ошибка API Google ({response.status_code}): {response.text}"
        except requests.exceptions.Timeout:
            if attempt == 2:
                return "⚠️ Превышено время ожидания ответа от Google. Попробуй повторить запрос."
            time.sleep(2)
        except Exception as e:
            return f"❌ Ошибка соединения: {e}"
            
    return "⚠️ Сервер Google временно перегружен (ошибка 503). Попробуй отправить сообщение еще раз через пару секунд."

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    bot.reply_to(message, "Привет! Бот на базе Gemini (прямой API) запущен и готов к работе.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    
    # Отправляем временное сообщение, пока думает нейросеть
    waiting_msg = bot.reply_to(message, "⏳ Думаю над ответом...")
    
    answer = ask_gemini(message.text)
    
    # Редактируем сообщение с ответом
    try:
        bot.edit_message_text(answer, chat_id=message.chat.id, message_id=waiting_msg.message_id)
    except Exception:
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
