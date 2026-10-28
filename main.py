import os
import threading
import time
from datetime import datetime, time as dtime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import dhanhq
from fastapi import FastAPI
import uvicorn
from contextlib import asynccontextmanager

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
IST = pytz.timezone("Asia/Kolkata")
dhan = dhanhq.dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

MAX_PREMIUM = 300
trade_log = []
active_trade = None

def get_oi_data(index_name):
    return 1250000, 850000, 0.9

def v24_filter(cand, ce_oi, pe_oi, pcr):
    if cand['ltp'] > MAX_PREMIUM: return False, "High Premium"
    if not cand.get("is_atm"): return False, "Not ATM"
    return True, f"ATM {cand['ltp']}<300 PCR {pcr:.2f} PASS"

def find_best():
    best_list = []
    for idx in ["NIFTY", "BANKNIFTY"]:
        ce_oi, pe_oi, pcr = get_oi_data(idx)
        cand = {"index": idx, "strike": 25200, "side": "PE", "ltp": 195, "is_atm": True, "full": f"{idx} 25200 PE @195", "score": 95}
        ok, reason = v24_filter(cand, ce_oi, pe_oi, pcr)
        if ok: best_list.append((cand, reason))
    return best_list

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("V24 Bot LIVE! 9:20-15:15 Auto Scan ON!")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    best = find_best()
    if not best: await update.message.reply_text("Koi V24 setup nahi <300 ATM"); return
    msg = "\n".join([f"{c['full']} - {r}" for c,r in best])
    await update.message.reply_text(f"V24 SCAN:\n{msg}")

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.run_polling()

def is_market_time():
    now = datetime.now(IST)
    if now.weekday() > 4: return False
    return dtime(9,20) <= now.time() <= dtime(15,15)

def auto_loop():
    while True:
        try:
            if is_market_time() and active_trade is None:
                best = find_best()
                if best: print(f"[{datetime.now(IST)}] ENTRY: {best[0][0]['full']}")
            time.sleep(60)
        except Exception as e:
            print(e); time.sleep(60)

@asynccontextmanager
async def lifespan(app: FastAPI):
    threading.Thread(target=auto_loop, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    print("V24 Bot Started - 9:20 to 3:15")
    yield

app = FastAPI(lifespan=lifespan)

@app.get("/")
def health():
    return {"status": "V24 Bot LIVE - 9:20 to 15:15", "time": str(datetime.now(IST))}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=10000)
