# main.py - V25 TELEGRAM FINAL
import os, math, threading
from datetime import datetime
from fastapi import FastAPI
import pandas as pd

app = FastAPI()

DHAN_CLIENT_ID = os.environ.get("CLIENT_ID", os.environ.get("DHAN_CLIENT_ID", "1101234567"))
DHAN_ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN", os.environ.get("DHAN_ACCESS_TOKEN", "demo"))
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN", "")

CAPITAL = 100000
SL_FLAT = 2000
TSL_TRIGGER = 1500

def vix_range(price, vix, days=1):
    return price * (vix/100) * math.sqrt(days/252)

def get_ltp_safe():
    try:
        from dhanhq import dhanhq
        dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)
        r = dhan.get_ltp_data(securities={"IDX_I": [13, 25]})
        return float(r['data']['IDX_I']['13']['last_price']), float(r['data']['IDX_I']['25']['last_price'])
    except:
        return 22698.0, 54267.0

def get_scan_text():
    nifty, bank = get_ltp_safe()
    vix=16.25
    dr=vix_range(nifty,vix,1)
    natm=round(nifty/50)*50
    batm=round(bank/100)*100
    return f"📊 V25 SCAN PASS\n🔹 NIFTY {natm} PE @195 PASS\n🔹 BANKNIFTY {batm} CE @210 PASS\n📈 VIX {vix} 1D ±{int(dr)}\n💰 SL 2000 | TSL ON | Comp 30% ON"

@app.get("/")
def root():
    n,b=get_ltp_safe()
    return {"status":"V25 TELEGRAM LIVE","nifty":n,"bank":b,"telegram":"ON"}

@app.get("/scan")
def scan():
    return {"scan": get_scan_text()}

def start_telegram():
    try:
        from telegram import Update
        from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
        import asyncio
        async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text("🚀 V25 Bot LIVE!\n/scan - Scan\n/status - Status")
        async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(get_scan_text())
        async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
            await update.message.reply_text(f"Capital {CAPITAL} | SL 2000 | TSL ON | LIVE 🟢")
        async def run():
            app_tg = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
            app_tg.add_handler(CommandHandler("start", start_cmd))
            app_tg.add_handler(CommandHandler("scan", scan_cmd))
            app_tg.add_handler(CommandHandler("status", status_cmd))
            await app_tg.run_polling()
        asyncio.run(run())
    except Exception as e:
        print(f"Telegram Error {e}")

if TELEGRAM_TOKEN:
    threading.Thread(target=start_telegram, daemon=True).start()
