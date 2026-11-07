import os
from threading import Thread
import telebot
from bs4 import BeautifulSoup
import google.generativeai as genai
from flask import Flask

# Настройка Flask-сервера для удержания порта Render
app = Flask(__name__)


@app.route("/")
def index():
  return "Bot is active with link parser!"


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
model = genai.GenerativeModel("gemini-1.5-flash")
bot = telebot.TeleBot(BOT_TOKEN)


def check_access(message):
  return message.from_user.id == USER_ID


@bot.message_handler(commands=["start"])
def send_welcome(message):
  if not check_access(message):
    return
  bot.reply_to(
      message,
      "Привет! Я на связи. Отправь мне текст или ссылку, и я сделаю"
      " суммаризацию.",
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if not check_access(message):
    return

  text = message.text

  try:
    # Проверяем, прислал ли пользователь ссылку
    if text.startswith("http://") or text.startswith("https://"):
      bot.reply_to(
          message, "⏳ Читаю и анализирую статью по ссылке, подожди секунду..."
      )

      # Загружаем содержимое страницы
      import requests

      headers = {"User-Agent": "Mozilla/5.0"}
      page = requests.get(text, headers=headers, timeout=10)
      soup = BeautifulSoup(page.text, "html.parser")

      # Вытаскиваем текст со страницы (параграфы)
      paragraphs = soup.find_all("p")
      article_text = " ".join([p.get_text() for p in paragraphs])

      if not article_text.strip():
        # Если тегов <p> нет, берем весь текст body
        article_text = soup.get_text()

      # Ограничиваем размер текста, чтобы не превысить лимиты модели
      article_text = article_text[:15000]

      prompt = f"Сделай краткую и четкую выжимку (summary) этой статьи на русском языке:\n\n{article_text}"
      response = model.generate_content(prompt)

      bot.reply_to(message, f"📌 **Краткая выжимка статьи:**\n\n{response.text}")

    else:
      # Обычный текстовый запрос без зависаний
      response = model.generate_content(text)
      bot.reply_to(message, response.text)

  except Exception as e:
    bot.reply_to(message, f"Ошибка при обработке: {e}")


if __name__ == "__main__":
  bot.infinity_polling(skip_pending=True)
