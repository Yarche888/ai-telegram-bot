import os
import sqlite3
from threading import Thread
import telebot
from bs4 import BeautifulSoup
import google.generativeai as genai
from flask import Flask

# Настройка Flask-сервера для удержания порта Render
app = Flask(__name__)


@app.route("/")
def index():
  return "Bot is active and running with memory!"


def run_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


# Запуск Flask-сервера в фоновом потоке
web_thread = Thread(target=run_web)
web_thread.daemon = True
web_thread.start()

# Переменные окружения
TOKEN = os.environ.get('BOT_TOKEN')  # или BOT_TOKEN
USER_ID = int(os.environ.get("USER_ID", 0))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_KEY)
# Используем актуальную модель серии Flash
model = genai.GenerativeModel("gemini-3.8-flash")
bot = telebot.TeleBot(TOKEN)


# Инициализация базы данных для памяти с ограничением истории
def init_db():
  conn = sqlite3.connect("chat_history.db")
  cursor = conn.cursor()
  cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    """)
  conn.commit()
  conn.close()


init_db()


def save_message(role, content):
  conn = sqlite3.connect("chat_history.db")
  cursor = conn.cursor()
  cursor.execute(
      "INSERT INTO messages (role, content) VALUES (?, ?)", (role, content)
  )
  conn.commit()
  conn.close()


def get_chat_history():
  conn = sqlite3.connect("chat_history.db")
  cursor = conn.cursor()
  # Загружаем только последние 10 сообщений для исключения тайм-аутов (504)
  cursor.execute(
      "SELECT role, content FROM messages ORDER BY id DESC LIMIT 10"
  )
  rows = cursor.fetchall()
  conn.close()

  history = []
  for role, content in reversed(rows):
    # Преобразуем роли под формат Gemini API
    gemini_role = "user" if role == "user" else "model"
    history.append({"role": gemini_role, "parts": [content]})
  return history


# Проверка доступа по личному Telegram ID
def check_access(message):
  return message.from_user.id == USER_ID


@bot.message_handler(commands=["start"])
def send_welcome(message):
  if not check_access(message):
    bot.reply_to(message, "У вас нет доступа к этому боту.")
    return
  bot.reply_to(
      message,
      "Привет! Я твой личный ИИ-ассистент Al Star ✨. Готов к работе!",
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if not check_access(message):
    return

  text = message.text

  try:
    save_message("user", text)

    # Передаем историю диалога в контекст модели
    chat = model.start_chat(history=get_chat_history())
    response = chat.send_message(text)

    save_message("model", response.text)
    bot.reply_to(message, response.text)

  except Exception as e:
    bot.reply_to(message, f"Произошла ошибка при обращении к ИИ: {e}")


if __name__ == "__main__":
  # skip_pending=True сбрасывает старые зависшие запросы и убирает конфликт 409
  bot.infinity_polling(skip_pending=True)
