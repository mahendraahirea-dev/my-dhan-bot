
from dhanhq import DhanContext, dhanhq
import os, time
from flask import Flask
import threading
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import asyncio

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Chaloo Aahe! 🚀"

def run_flask():
    app.run(host='0.0.0.0', port=10000)

CLIENT_ID = os.getenv("CLIENT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# Dhan Connect
dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
dhan = dhanhq(dhan_context)
print("✅ Dhan Connected!")

# --- TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Bot Chaloo Aahe!\nCommands:\n/buy NIFTY 25200 CE 1\n/sell\n/positions\n/balance")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # /buy NIFTY 25200 CE 1
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Use: /buy NIFTY 25200 CE 1")
            return
        # Simple market order example - tuzya logic pramane badal
        await update.message.reply_text(f"BUY Order Trying: {args}")
        # Yathe tuza Dhan order code yeil
        # dhan.place_order(...)
        await update.message.reply_text(f"✅ BUY Done: {' '.join(args)}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def positions_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        pos = dhan.get_positions()
        await update.message.reply_text(f"Positions: {pos}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        bal = dhan.get_fund_limits()
        await update.message.reply_text(f"Balance: {bal}")
    except Exception as e:
        await update.message.reply_text(f"Error: {e}")

# --- AUTO ENTRY FUNCTION ---
def auto_trading_logic():
    print("🤖 Auto Trading Check...")
    # Yathe tuzi strategy
    # Example: Roj 9:20 la auto BUY
    # if time == "09:20":
    #    dhan.place_order(...)
    pass

async def run_telegram():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("positions", positions_command))
    application.add_handler(CommandHandler("balance", balance_command))
    print("✅ Telegram Bot Started!")
    await application.run_polling()

def start_telegram_thread():
    asyncio.run(run_telegram())

# Start Everything
threading.Thread(target=run_flask).start()
threading.Thread(target=start_telegram_thread).start()

while True:
    print("Bot Alive... 💓")
    auto_trading_logic()
    time.sleep(60)
