import os
from threading import Thread
import telebot
from flask import Flask
import google.generativeai as genai

# Мини-веб-сервер для удовлетворения требований Render к портам
app = Flask('')


@app.route('/')
def home():
  return 'Bot is active and running!'


def run_web():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


# Запуск веб-сервера в фоновом потоке
Thread(target=run_web).daemon = True

# Инициализация бота и Gemini
TOKEN = os.environ.get('BOT_TOKEN')
USER_ID = int(os.environ.get('USER_ID', 0))
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-pro')

bot = telebot.TeleBot(TOKEN)


@bot.message_handler(commands=['start'])
def send_welcome(message):
  if message.from_user.id != USER_ID:
    return
  bot.reply_to(
      message,
      'Привет! Я твой личный ИИ-ассистент на базе Gemini Pro. Готов к работе'
      ' 24/7.',
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if message.from_user.id != USER_ID:
    return
  try:
    response = model.generate_content(message.text)
    bot.reply_to(message, response.text)
  except Exception as e:
    bot.reply_to(message, f'Произошла ошибка при обращении к ИИ: {e}')


if __name__ == '__main__':
  bot.infinity_polling()
