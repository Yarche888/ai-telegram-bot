import os
from threading import Thread
import telebot
import google.generativeai as genai
from flask import Flask

# Настройка Flask-сервера для удержания порта Render
app = Flask(__name__)


@app.route("/")
def index():
  return "Bot is active!"


def run_web():
  port = int(os.environ.get("PORT", 10000))
  app.run(host="0.0.0.0", port=port)


web_thread = Thread(target=run_web)
web_thread.daemon = True
web_thread.start()

# Переменные окружения
BOT_TOKEN = os.environ.get("BOT_TOKEN")
USER_ID = int(os.environ.get("USER_ID", 0))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-3.8-flash")
bot = telebot.TeleBot(BOT_TOKEN)


def check_access(message):
  return message.from_user.id == USER_ID


@bot.message_handler(commands=["start"])
def send_welcome(message):
  if not check_access(message):
    return
  bot.reply_to(message, "Привет! Я на связи и готов работать без зависаний.")


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if not check_access(message):
    return

  try:
    # Отправляем запрос напрямую модели без истории, чтобы исключить 504 ошибку
    response = model.generate_content(message.text)
    bot.reply_to(message, response.text)
  except Exception as e:
    bot.reply_to(message, f"Ошибка: {e}")


if __name__ == "__main__":
  bot.infinity_polling(skip_pending=True)




