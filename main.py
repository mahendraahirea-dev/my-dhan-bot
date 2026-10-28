from fastapi import FastAPI
from datetime import datetime
from zoneinfo import ZoneInfo
import math, os, asyncio
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import uvicorn

# Support both names - ACCESS_TOKEN or DHAN_ACCESS_TOKEN
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN") or os.getenv("BOT_TOKEN")
DHAN_TOKEN = os.getenv("ACCESS_TOKEN") or os.getenv("DHAN_ACCESS_TOKEN")
DHAN_CLIENT = os.getenv("CLIENT_ID") or os.getenv("DHAN_CLIENT_ID")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID") or os.getenv("TELEGRAM_CHAT_")

IST = ZoneInfo("Asia/Kolkata")

def calc_expected_move(nifty_price, vix, days=1):
    return round(nifty_price * (vix/100) * math.sqrt(days/252))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    n=25000
    v=14.5
    m1=calc_expected_move(n,v,1)
    m5=calc_expected_move(n,v,5)
    await update.message.reply_text(f"🚀 V24 Bot LIVE! 🟢\n\n📊 VIX FORMULA: Nifty*VIX/100*sqrt(N/252)\nNifty {n} VIX {v}\n1D: ±{m1} ({n-m1} to {n+m1})\n1W: ±{m5}\n\n/scan - V24 Scan\n/range 25000 15 - Custom\n\nToken OK: {bool(TELEGRAM_TOKEN)}")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("V24 SCAN <300 ATM:\nNIFTY 25200 PE @195 - PASS\nBANKNIFTY 57000 CE @210 - PASS\n\nReal Dhan API pudhcha step la!")

async def range_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n=float(context.args[0]) if len(context.args)>0 else 25000
        v=float(context.args[1]) if len(context.args)>1 else 15
        d=int(context.args[2]) if len(context.args)>2 else 1
        m=calc_expected_move(n,v,d)
        await update.message.reply_text(f"Nifty {n} VIX {v} {d}D\nMove ±{m}\nRange {n-m} to {n+m}\n\nNote: VIX shows Size, Not Direction!")
    except:
        await update.message.reply_text("Use: /range 25000 15")

async def run_telegram():
    if not TELEGRAM_TOKEN:
        print("No TELEGRAM_TOKEN found!")
        return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("range", range_cmd))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print(f"Telegram LIVE - Token found!")
    while True: await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_telegram())
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    m1=calc_expected_move(25000,15,1)
    return {"status": "LIVE 🟢 V24+Telegram+VIX FIXED", "1D_Range": f"±{m1}", "formula": "Nifty*VIX/100*sqrt(N/252)", "env_check": {"TELEGRAM_TOKEN": bool(TELEGRAM_TOKEN), "ACCESS_TOKEN": bool(DHAN_TOKEN), "CLIENT_ID": bool(DHAN_CLIENT)}, "time": str(datetime.now(IST))}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
