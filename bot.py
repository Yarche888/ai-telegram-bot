import os
import telebot
import google.generativeai as genai

TOKEN = os.environ.get("BOT_TOKEN")
ALLOWED_USER_ID = int(os.environ.get("USER_ID", 0))
GEMINI_KEY = os.environ.get("GEMINI_API_KEY")

genai.configure(api_key=GEMINI_KEY)
model = genai.GenerativeModel("gemini-1.5-flash")

bot = telebot.TeleBot(TOKEN)

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    if message.from_user.id != ALLOWED_USER_ID:
        bot.reply_to(message, "Доступ запрещен. Этот бот личный.")
        return
    bot.reply_to(message, "Привет! Я твой личный ИИ-ассистент на базе Gemini. Готов к работе 24/7.")

@bot.message_handler(func=lambda message: True)
def handle_message(message):
    if message.from_user.id != ALLOWED_USER_ID:
        return
    
    bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        response = model.generate_content(message.text)
        bot.reply_to(message, response.text)
    except Exception as e:
        bot.reply_to(message, f"Произошла ошибка при обращении к ИИ: {e}")

if __name__ == "__main__":
    print("Бот запущен и ожидает сообщения...")
    bot.infinity_polling()
