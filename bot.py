import os
import time
from threading import Thread
import telebot
import requests
from bs4 import BeautifulSoup
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

bot = telebot.TeleBot(BOT_TOKEN)

def check_access(message):
    return message.from_user.id == USER_ID

def ask_gemini(prompt_text):
    """Прямой запрос к актуальной модели через стабильный эндпоинт"""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash-latest:generateContent?key={GEMINI_KEY}"
    headers = {"Content-Type": "application/json"}
    payload = {
        "contents": [{
            "parts": [{"text": prompt_text}]
        }]
    }
    
    response = requests.post(url, json=payload, headers=headers, timeout=15)
    if response.status_code == 200:
        data = response.json()
        try:
            return data["candidates"][0]["content"]["parts"][0]["text"]
        except Exception:
            return "Получен странный ответ от модели."
    else:
        return f"Ошибка API Google ({response.status_code}): {response.text}"

@bot.message_handler(commands=["start"])
def send_welcome(message):
    if not check_access(message):
        return
    bot.reply_to(message, "Привет! Бот на базе Gemini (прямой API) запущен и готов к работе.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_access(message):
        return
        
    text = message.text.strip()
    
    try:
        # Обработка ссылок
        if text.startswith("http://") or text.startswith("https://"):
            bot.reply_to(message, "⏳ Читаю статью, подожди секунду...")
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            page = requests.get(text, headers=headers, timeout=8)
            soup = BeautifulSoup(page.text, "html.parser")
            
            paragraphs = soup.find_all("p")
            article_text = " ".join([p.get_text() for p in paragraphs])
            if not article_text.strip():
                article_text = soup.get_text()
                
            article_text = article_text[:4000]
            prompt = f"Сделай краткую и четкую выжимку (summary) статьи:\n\n{article_text}"
            
            answer = ask_gemini(prompt)
            bot.reply_to(message, f"📌 **Выжимка статьи:**\n\n{answer}")
        else:
            # Обычный текст
            answer = ask_gemini(text)
            bot.reply_to(message, answer)
            
    except Exception as e:
        print("Ошибочка:", e)
        bot.reply_to(message, f"❌ Реальная ошибка: {e}")

if __name__ == "__main__":
    print("⏳ Ожидание завершения предыдущих сессий...")
    time.sleep(3)
    
    print("🚀 Запуск ручного пуллинга бота...")
    bot.remove_webhook()
    
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
