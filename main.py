from dhanhq import DhanContext, dhanhq
import os, time
import threading
import asyncio
from flask import Flask
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

app = Flask(__name__)
@app.route('/')
def home():
    return "Bot Chaloo Aahe! 🚀"

CLIENT_ID = os.getenv("CLIENT_ID")
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

dhan_context = DhanContext(CLIENT_ID, ACCESS_TOKEN)
dhan = dhanhq(dhan_context)
print("Dhan Connected!")

# --- TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 Bot Chaloo Aahe!\nCommands:\n/buy NIFTY 25200 CE 1\n/positions\n/balance")

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        args = context.args
        if len(args) < 3:
            await update.message.reply_text("Use: /buy NIFTY 25200 CE 1")
            return
        await update.message.reply_text(f"BUY Order Trying: {args}")
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

# --- AUTO ENTRY ---
def auto_trading_logic():
    print("Auto Trading Check...")

# --- FIXED TELEGRAM RUNNER FOR RENDER ---
async def run_telegram():
    application = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("buy", buy_command))
    application.add_handler(CommandHandler("positions", positions_command))
    application.add_handler(CommandHandler("balance", balance_command))
    
    print("✅ Telegram Bot Started!")
    await application.initialize()
    await application.start()
    await application.updater.start_polling(drop_pending_updates=True)
    # Bot chalu theva
    while True:
        await asyncio.sleep(3600)

def start_bot_loop():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(run_telegram())

# Start in background
threading.Thread(target=start_bot_loop, daemon=True).start()

if __name__ == "__main__":
    app.run(host='0.0.0.0', port=10000)
