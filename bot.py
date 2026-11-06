import os
import re
from threading import Thread
from bs4 import BeautifulSoup
from apscheduler.schedulers.background import BackgroundScheduler
import pytz
import requests
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


# Утренняя сводка (08:00 по Киеву)
def send_morning_digest():
  if not USER_ID:
    return
  try:
    prompt = (
        'Напиши бодрое утреннее приветствие, задай фокус на продуктивность и'
        ' дай 1 ценный совет на день.'
    )
    response = model.generate_content(prompt)
    bot.send_message(
        USER_ID, f'🌅 **Утренняя сводка дня:**\n\n{response.text}'
    )
  except Exception as e:
    bot.send_message(USER_ID, f'Ошибка утренней сводки: {e}')


# Вечерняя сводка (21:00 по Киеву)
def send_evening_digest():
  if not USER_ID:
    return
  try:
    prompt = (
        'Напиши спокойное вечернее подведение итогов, пожелай хорошего отдыха'
        ' и задай один вопрос для рефлексии прошедшего дня.'
    )
    response = model.generate_content(prompt)
    bot.send_message(
        USER_ID, f'🌙 **Вечерняя сводка и итоги:**\n\n{response.text}'
    )
  except Exception as e:
    bot.send_message(USER_ID, f'Ошибка вечерней сводки: {e}')


# Настройка планировщика
scheduler = BackgroundScheduler(timezone=pytz.timezone('Europe/Kyiv'))
scheduler.add_job(send_morning_digest, 'cron', hour=8, minute=0)
scheduler.add_job(send_evening_digest, 'cron', hour=21, minute=0)
scheduler.start()


@bot.message_handler(commands=['start'])
def send_welcome(message):
  if message.from_user.id != USER_ID:
    return
  bot.reply_to(
      message,
      'Привет! Твой личный ИИ-ассистент на Gemini Pro запущен. Умею делать'
      ' саммари по ссылкам, присылать утренние и вечерние сводки! 🚀',
  )


@bot.message_handler(func=lambda message: True)
def handle_message(message):
  if message.from_user.id != USER_ID:
    return

  text = message.text.strip()
  url_match = re.search(r'https?://[^\s]+', text)

  if url_match:
    url = url_match.group(0)
    bot.reply_to(message, '🔗 Читаю статью по ссылке и делаю выжимку...')
    try:
      headers = {'User-Agent': 'Mozilla/5.0'}
      page = requests.get(url, headers=headers, timeout=10)
      soup = BeautifulSoup(page.content, 'html.parser')

      for script in soup(['script', 'style', 'nav', 'footer', 'header']):
        script.decompose()

      page_text = soup.get_text(separator=' ', strip=True)
      if len(page_text) > 15000:
        page_text = page_text[:15000]

      prompt = (
          f'Проанализируй текст веб-страницы и составь краткую выжимку'
          f' (Summary) ровно в 5 ключевых тезисах на русском языке:\n\n{page_text}'
      )
      response = model.generate_content(prompt)

      bot.reply_to(
          message,
          f'📄 **Краткая выжимка статьи:**\n\n{response.text}',
          parse_mode='Markdown',
      )
    except Exception as e:
      bot.reply_to(message, f'Не удалось обработать ссылку. Ошибка: {e}')
  else:
    try:
      response = model.generate_content(text)
      bot.reply_to(message, response.text)
    except Exception as e:
      bot.reply_to(message, f'Произошла ошибка при обращении к ИИ: {e}')


if __name__ == '__main__':
  bot.infinity_polling()
