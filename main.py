import os, threading, time
from flask import Flask
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
print(f"BOT_TOKEN loaded = {'Yes' if BOT_TOKEN else 'No'}")

app = Flask(__name__)

def get_best_signal():
    return "BEST: NIFTY 24600 @ 192Rs\nENTRY NIFTY 24600 @ 192"

@app.route('/')
def home():
    return f"Bot is Live! {get_best_signal()}"

bot = None
if BOT_TOKEN:
    bot = telebot.TeleBot(BOT_TOKEN)
    
    @bot.message_handler(commands=['start','help','best'])
    def handle_start(message):
        print(f"Received {message.text} from {message.chat.id}")
        signal = get_best_signal()
        bot.reply_to(message, f"🚀 Dhan Bot Live!\n\n{signal}")

    @bot.message_handler(func=lambda m: True)
    def handle_all(message):
        bot.reply_to(message, f"Hi! /start dya\n{get_best_signal()}")

    def run_bot():
        print(">>> Starting Telegram polling...")
        while True:
            try:
                bot.infinity_polling(timeout=60)
            except Exception as e:
                print(f"Bot crashed: {e}")
                time.sleep(5)

    threading.Thread(target=run_bot, daemon=True).start()
else:
    print("!!! BOT_TOKEN missing!")

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
