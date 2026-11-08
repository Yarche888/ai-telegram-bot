import os
import time
from threading import Thread
from datetime import datetime, timedelta
import telebot
from flask import Flask
from google import genai
from google.genai.errors import APIError
from apscheduler.schedulers.background import BackgroundScheduler

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

# Инициализируем планировщик для будильников и напоминаний
scheduler = BackgroundScheduler()
scheduler.start()

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

def trigger_alarm(chat_id, text):
    """Функция будильника, которая сработает в назначенное время"""
    try:
        bot.send_message(
            chat_id, 
            f"⏰ **Вставай! Время пришло!**\n\n💬 Заметка: {text}", 
            parse_mode="Markdown"
        )
    except Exception as e:
        print(f"⚠️ Ошибка отправки будильника: {e}")

@bot.message_handler(commands=['start'])
def send_welcome(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    bot.reply_to(
        message, 
        "Привет! Бот на агенте (v1beta) запущен и готов к работе.\n\n"
        "⏰ Чтобы поставить будильник, используй команду:\n"
        "`/alarm ЧЧ:ММ Текст напоминания` (например: `/alarm 07:30 Вставать и пить кофе`)",
        parse_mode="Markdown"
    )

@bot.message_handler(commands=['alarm'])
def set_alarm(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    
    args = message.text.split(maxsplit=2)
    if len(args) < 2:
        bot.reply_to(
            message, 
            "⚠️ Укажи время в формате ЧЧ:ММ. Пример:\n`/alarm 07:30 Вставать!`", 
            parse_mode="Markdown"
        )
        return
    
    time_str = args[1]
    alarm_text = args[2] if len(args) > 2 else "Пора просыпаться!"
    
    try:
        now = datetime.now()
        alarm_time = datetime.strptime(time_str, "%H:%M").replace(
            year=now.year, month=now.month, day=now.day
        )
        
        # Если указанное время уже прошло сегодня, ставим на завтра
        if alarm_time <= now:
            alarm_time += timedelta(days=1)
            
        # Добавляем задачу в планировщик
        scheduler.add_job(
            trigger_alarm, 
            'date', 
            run_date=alarm_time, 
            args=[message.chat.id, alarm_text]
        )
        
        bot.reply_to(
            message, 
            f"✅ Будильник успешно установлен на **{alarm_time.strftime('%Y-%m-%d %H:%M')}**!", 
            parse_mode="Markdown"
        )
        
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат времени. Используй ЧЧ:ММ (например, 07:30).")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if not check_access(message):
        bot.reply_to(message, "Доступ запрещен.")
        return
    
    status_msg = bot.reply_to(message, "⏳ Секунду, агент анализирует запрос...")
    ai_response = ask_gemini(message.text)
    
    try:
        bot.edit_message_text(
            chat_id=message.chat.id,
            message_id=status_msg.message_id,
            text=ai_response
        )
    except Exception:
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
