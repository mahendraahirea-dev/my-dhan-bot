from fastapi import FastAPI
from datetime import datetime, time as dtime
from zoneinfo import ZoneInfo
import math, os, asyncio
from contextlib import asynccontextmanager
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import uvicorn

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
IST = ZoneInfo("Asia/Kolkata")

def calc_expected_move(nifty_price, vix, days=1):
    return round(nifty_price * (vix/100) * math.sqrt(days/252))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nifty=25000
    vix=14.5
    m1=calc_expected_move(nifty,vix,1)
    m5=calc_expected_move(nifty,vix,5)
    await update.message.reply_text(
        f"🚀 V24 Bot LIVE! 🟢\n\n"
        f"📊 VIX FORMULA: Nifty * VIX/100 * sqrt(N/252)\n"
        f"Nifty {nifty} VIX {vix}\n"
        f"1D: ±{m1} ({nifty-m1} to {nifty+m1})\n"
        f"1W: ±{m5}\n\n"
        f"/scan - V24 Scan\n"
        f"/range 25000 15 - Custom"
    )

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("V24 SCAN <300 ATM:\nNIFTY 25200 PE @195 - PASS\nBANKNIFTY 57000 CE @210 - PASS")

async def range_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        n=float(context.args[0]) if len(context.args)>0 else 25000
        v=float(context.args[1]) if len(context.args)>1 else 15
        d=int(context.args[2]) if len(context.args)>2 else 1
        m=calc_expected_move(n,v,d)
        await update.message.reply_text(f"Nifty {n} VIX {v} {d}D\nMove ±{m}\nRange {n-m} to {n+m}")
    except:
        await update.message.reply_text("Use: /range 25000 15")

async def run_telegram():
    if not TELEGRAM_TOKEN: return
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.add_handler(CommandHandler("range", range_cmd))
    await app.initialize()
    await app.start()
    await app.updater.start_polling()
    print("Telegram LIVE")
    while True: await asyncio.sleep(3600)

@asynccontextmanager
async def lifespan(app: FastAPI):
    asyncio.create_task(run_telegram())
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def home():
    now=datetime.now(IST)
    m1=calc_expected_move(25000,15,1)
    return {"status": "LIVE 🟢 V24+Telegram+VIX", "time": str(now), "1D_Range": f"24764 to 25236 (±{m1})", "formula": "Nifty*VIX/100*sqrt(N/252)", "telegram": "Bot Started"}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
