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

# Инициализируем клиент с принудительным использованием v1beta API
client = genai.Client(
    api_key=GEMINI_KEY,
    http_options={'api_version': 'v1beta'}
)

bot = telebot.TeleBot(BOT_TOKEN)

def check_access(message):
    return message.from_user.id == USER_ID

def ask_gemini(prompt_text, retries=3, delay=5):
    """Запрос через управляемого агента с версией v1beta"""
    for attempt in range(retries):
        try:
            interaction = client.interactions.create(
                agent="antigravity-preview-09-2026",
                input=prompt_text,
                environment="remote"
            )
            if interaction and interaction.output_text:
                return interaction.output_text
            else:
                return "⚠️ Агент вернул пустой ответ."
        except APIError as e:
            if "429" in str(e) or "ResourceExhausted" in str(e):
                if attempt < retries - 1:
                    print(f"⚠️ Превышен лимит запросов (429). Ждем {delay} сек...")
                    time.sleep(delay)
                    continue
                else:
                    return "❌ Лимит запросов исчерпан, попробуй позже."
            else:
                return f"❌ Ошибка API Gemini: {e}"
        except Exception as e:
            return f"❌ Ошибка при обращении к агенту: {e}"

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    bot.reply_to(message, "Привет! Бот на агенте (v1beta) запущен и готов к работе.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    
    # Отправляем предварительный статус, чтобы видеть, что запрос принят
    status_msg = bot.reply_to(message, "⏳ Секунду, агент анализирует запрос...")
    
    # Получаем ответ от агента (может занять время при сложном поиске)
    ai_response = ask_gemini(message.text)
    
    try:
        # Редактируем статусное сообщение на финальный результат
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text=ai_response
        )
    except Exception:
        # Если отредактировать не получилось, отправляем новым сообщением
        bot.reply_to(message, ai_response)

# Настройка Flask для Render и Keep-Alive пингера
app = Flask(__name__)

@app.route('/')
def index():
    return "Bot is running!"

def run_flask():
    app.run(host="0.0.0.0", port=10000)

if __name__ == "__main__":
    print("⏳ Ожидание завершения предыдущих сессий...")
    time.sleep(3)

    print("🔄 Сбрасываем вебхуки и запускаем пуллинг...")
    bot.remove_webhook()
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except Exception:
        pass

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
