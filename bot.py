import os
from threading import Thread
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import telebot
from flask import Flask
import google.generativeai as genai

# Flask для Render
app = Flask('')


@app.route('/')
def home():
  return 'Bot is active and running!'


def run_web():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


Thread(target=run_web).daemon = True

# Переменные
TOKEN = os.environ.get('BOT_TOKEN')
USER_ID = int(os.environ.get('USER_ID', 0))
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-pro')
bot = telebot.TeleBot(TOKEN)


# Функция утреннего будильника
def send_morning_wake_up():
  if not USER_ID:
    return
  try:
    prompt = (
        'Напиши бодрое, энергичное и короткое утреннее приветствие и 1 полезную'
        ' мысль или совет на день.'
    )
    response = model.generate_content(prompt)
    bot.send_message(USER_ID, f'⏰ **Утренний будильник!**\n\n{response.text}')
  except Exception as e:
    bot.send_message(USER_ID, f'Ошибка утреннего будильника: {e}')


# Настройка планировщика (время 07:30, часовой пояс Europe/Kyiv)
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Kyiv'))
scheduler.add_job(send_morning_wake_up, 'cron', hour=8, minute=00)
scheduler.start()


@bot.message_handler(commands=['start'])
def send_welcome(message):
  if message.from_user.id != USER_ID:
    return
  bot.reply_to(
      message,
      'Привет! Я твой личный ИИ-ассистент на базе Gemini Pro с функцией'
      ' утреннего будильника! ⏰',
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
