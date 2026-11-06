import os
import re
import sqlite3
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
  return 'Bot is active and running with memory!'


# Запуск Flask-сервера в фоновом потоке сразу при старте,
# чтобы Render мгновенно фиксировал открытый порт
def run_web():
  port = int(os.environ.get('PORT', 10000))
  app.run(host='0.0.0.0', port=port)


web_thread = Thread(target=run_web)
web_thread.daemon = True
web_thread.start()

# Переменные окружения
TOKEN = os.environ.get('BOT_TOKEN')
USER_ID = int(os.environ.get('USER_ID', 0))
GEMINI_KEY = os.environ.get('GEMINI_API_KEY')

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel('gemini-2.5-pro')
bot = telebot.TeleBot(TOKEN)


# Инициализация базы данных для памяти
def init_db():
  conn = sqlite3.connect('chat_history.db')
  cursor = conn.cursor()
  cursor.execute('''
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            role TEXT,
            content TEXT
        )
    ''')
  conn.commit()
  conn.close()


init_db()


# Сохранение сообщения в базу
def save_message(role, content):
  conn = sqlite3.connect('chat_history.db')
  cursor = conn.cursor()
  cursor.execute(
      'INSERT INTO messages (role, content) VALUES (?, ?)', (role, content)
  )
  conn.commit()
  conn.close()


# Загрузка последних сообщений для контекста (последние 10 штук)
def get_chat_history():
  conn = sqlite3.connect('chat_history.db')
  cursor = conn.cursor()
  cursor.execute('SELECT role, content FROM messages ORDER BY id DESC LIMIT 10')
  rows = cursor.fetchall()
  conn.close()

  history = []
  for role, content in reversed(rows):
    history.append({'role': role, 'parts': [content]})
  return history


# Утренняя и вечерняя сводки
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
    save_message('model', response.text)
  except Exception as e:
    bot.send_message(USER_ID, f'Ошибка утренней сводки: {e}')


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
    save_message('model', response.text)
  except Exception as e:
    bot.send_message(USER_ID, f'Ошибка вечерней сводки: {e}')


# Планировщик
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
      'Привет! Твой ИИ-ассистент с памятью, саммари ссылок и сводками готов к'
      ' работе! 🚀',
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
      save_message('user', f'Скинул ссылку: {url}')
      save_message('model', response.text)
    except Exception as e:
      bot.reply_to(message, f'Не удалось обработать ссылку. Ошибка: {e}')
  else:
    try:
      save_message('user', text)

      chat = model.start_chat(history=get_chat_history())
      response = chat.send_message(text)

      save_message('model', response.text)

      bot.reply_to(message, response.text)
    except Exception as e:
      bot.reply_to(message, f'Произошла ошибка при обращении к ИИ: {e}')


if __name__ == '__main__':
  bot.infinity_polling()
