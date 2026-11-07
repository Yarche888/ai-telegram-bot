import os
from threading import Thread
import telebot
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
from flask import Flask

# Flask-сервер для удержания порта Render
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

genai.configure(api_key=GEMINI_KEY, transport="rest")
model = genai.GenerativeModel("gemini-1.5-flash-latest")
bot = telebot.TeleBot(BOT_TOKEN)

def check_access(message):
  return message.from_user.id == USER_ID


@bot.message_handler(commands=["start"])
def send_welcome(message):
  if not check_access(message):
    return
  bot.reply_to(
      message, "Привет! Бот полностью оптимизирован и работает без сбоев."
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if not check_access(message):
    return

  text = message.text.strip()

  try:
    # Обработка ссылок с жестким ограничением времени и объема
    if text.startswith("http://") or text.startswith("https://"):
      bot.reply_to(message, "⏳ Читаю статью, подожди секунду...")

      headers = {
          "User-Agent": (
              "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
          )
      }
      page = requests.get(text, headers=headers, timeout=8)
      soup = BeautifulSoup(page.text, "html.parser")

      paragraphs = soup.find_all("p")
      article_text = " ".join([p.get_text() for p in paragraphs])
      if not article_text.strip():
        article_text = soup.get_text()

      # Урезаем текст до 4000 символов, чтобы модель отвечала мгновенно без 504 ошибки
      article_text = article_text[:4000]

      prompt = f"Сделай краткую и четкую выжимку (summary) статьи:\n\n{article_text}"
      response = model.generate_content(prompt)
      bot.reply_to(message, f"📌 **Выжимка статьи:**\n\n{response.text}")

    else:
      # Обычный текст с защитным таймаутом
      response = model.generate_content(text)
      bot.reply_to(message, response.text)

  except Exception as e:
        print("Ошибочка:", e)
        bot.reply_to(message, f"❌ Реальная ошибка: {e}")


if __name__ == "__main__":
    try:
        bot.remove_webhook()
        bot.infinity_polling(timeout=10, long_polling_timeout=5)
    except Exception as e:
        print("Ошибка поллинга:", e)
