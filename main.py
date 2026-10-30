import os
import threading
import time
from fastapi import FastAPI
from datetime import datetime

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("TELEGRAM_BOT_TOKEN")

app = FastAPI(title="my-dhan-bot V36 FINAL")

def run_telegram_bot():
    try:
        import telebot
        print(">>> TELEGRAM: Bot created")
        if not TELEGRAM_TOKEN:
            print(">>> TELEGRAM ERROR: Token not found!")
            return
        
        bot = telebot.TeleBot(TELEGRAM_TOKEN, threaded=False)
        
        @bot.message_handler(commands=['start','status','today','auto_on'])
        def handle_all(message):
            chat_id = message.chat.id
            print(f">>> CMD: {message.text}")
            reply = f"""✅ V36 FINAL LIVE
Time: {datetime.now()}
Cmd: {message.text}
Status: PAPER | 1 LOT | SL 1500
Live: https://my-dhan-bot.onrender.com
Bot is running perfectly!"""
            bot.send_message(chat_id, reply)

        bot.remove_webhook()
        time.sleep(1)
        print(">>> TELEGRAM POLLING STARTED...")
        bot.infinity_polling(timeout=60, long_polling_timeout=60)
        
    except Exception as e:
        print(f">>> TELEGRAM ERROR: {e}")
        time.sleep(10)
        run_telegram_bot()

@app.on_event("startup")
def startup_event():
    t = threading.Thread(target=run_telegram_bot, daemon=True)
    t.start()
    print(">>> Telegram Thread Started")

@app.get("/")
def home():
    return {
        "status": "V36 - FINAL LAST & BEST",
        "live": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "telegram": "polling",
        "mode": "PAPER"
    }
