# Минимальный бот — только ответ на /start. Запуск: python start_test_bot.py
# Если этот бот отвечает, токен и выбор бота верные. Если нет — откройте в BotFather того бота, которому пишете, и вставьте его токен в .env

import os
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env"))
token = (os.getenv("TELEGRAM_TOKEN") or "").strip()

if not token or len(token) < 20:
    print("Ошибка: в .env нет TELEGRAM_TOKEN или он короткий. Добавьте токен от @BotFather.")
    exit(1)

# Узнаём имя бота по токену
import urllib.request
import json
try:
    r = urllib.request.urlopen(f"https://api.telegram.org/bot{token}/getMe", timeout=5)
    data = json.loads(r.read().decode())
    if data.get("ok"):
        username = data["result"].get("username", "?")
        print("Бот:", username)
        print("Откройте в Telegram: t.me/" + username)
        print("Напишите ему /start")
    else:
        print("Токен неверный или отозван. Получите новый в @BotFather.")
        exit(1)
except Exception as e:
    print("Нет связи с Telegram или неверный токен:", e)
    exit(1)

from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    chat_id = update.effective_chat.id
    await context.bot.send_message(chat_id=chat_id, text="Работает. Старт получен.")

app = ApplicationBuilder().token(token).build()
app.add_handler(CommandHandler("start", start))
print("Ожидаю сообщения... (Ctrl+C — выход)")
app.run_polling()
