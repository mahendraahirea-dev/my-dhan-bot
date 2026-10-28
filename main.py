import os
import threading
import time
from datetime import datetime, date, time as dtime
import pytz
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
import dhanhq
from openpyxl import Workbook
from fastapi import FastAPI
import uvicorn

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
IST = pytz.timezone("Asia/Kolkata")

dhan = dhanhq.dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

# ===== V24 FINAL RULE - LOCKED =====
MAX_PREMIUM = 300  # 300 chya aat jo ATM asel toch
LOT_SIZE = 15
LOTS = 1
COST_LOCK = 20
TRAIL_PCT = 0.30
AUTO_EXIT = 120000

trade_log = []
active_trade = None

def get_oi_data(index_name):
    """OI Data fetch - Dhan se"""
    try:
        # Dhan option chain se OI nikalna
        # Real me: dhan.get_option_chain(expiry, index)
        ce_oi = 1250000  # Mock - real API se ayega
        pe_oi = 850000
        pcr = pe_oi / ce_oi if ce_oi>0 else 1.0
        return ce_oi, pe_oi, pcr
    except:
        return 0, 0, 1.0

def v24_filter(cand, ce_oi, pe_oi, pcr):
    ltp = cand['ltp']
    # Rule 1: ATM + <300
    if ltp > MAX_PREMIUM:
        return False, f"Premium {ltp}>300 Skip"
    if not cand.get("is_atm"):
        return False, "Not ATM"
    # Rule 2: PCR Filter + OI
    if cand['side'] == 'PE' and pcr > 1.0:
        return False, f"PCR {pcr:.2f} Bullish - PE nako"
    if cand['side'] == 'CE' and pcr < 1.0:
        return False, f"PCR {pcr:.2f} Bearish - CE nako"
    if 0.8 < pcr < 1.2:
        return False, f"PCR {pcr:.2f} Sideways - No Trade"
    return True, f"ATM {ltp}<300 PASS CE_OI {ce_oi//1000}k PE_OI {pe_oi//1000}k PCR {pcr:.2f}"

def find_best():
    indices = ["NIFTY", "BANKNIFTY", "SENSEX"]
    best_list = []
    for idx in indices:
        ce_oi, pe_oi, pcr = get_oi_data(idx)
        for side in ["CE", "PE"]:
            cand = {
                "index": idx,
                "strike": 25200,
                "side": side,
                "ltp": 195,
                "is_atm": True,
                "ce_oi": ce_oi,
                "pe_oi": pe_oi,
                "pcr": pcr,
                "full": f"{idx} ATM 25200 {side}",
                "score": 95
            }
            ok, reason = v24_filter(cand, ce_oi, pe_oi, pcr)
            if ok:
                best_list.append((cand, reason))
    return best_list

# ===== TELEGRAM COMMANDS =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("V24 Bot LIVE! 9:20-3:15 Auto Scan ON hai! /scan kar")

async def scan(update: Update, context: ContextTypes.DEFAULT_TYPE):
    best = find_best()
    if not best:
        await update.message.reply_text("Koi V24 setup nahi <300 ATM")
        return
    msg = "\n".join([f"{c['full']} - {r}" for c,r in best])
    await update.message.reply_text(f"V24 SCAN:\n{msg}")

def run_bot():
    app = ApplicationBuilder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("scan", scan))
    app.run_polling()

# ===== MAIN AUTO LOOP - 9:20 to 15:15 =====
def is_market_time():
    now = datetime.now(IST)
    # Mon-Fri only
    if now.weekday() > 4:
        return False
    start_t = dtime(9, 20)
    end_t = dtime(15, 15)
    return start_t <= now.time() <= end_t

def auto_loop():
    global active_trade
    while True:
        try:
            if is_market_time():
                if active_trade is None:
                    best = find_best()
                    if best:
                        cand, reason = best[0]
                        print(f"[{datetime.now(IST)}] ENTRY SIGNAL: {cand['full']} | {reason}")
                        # yaha pe Dhan order place karna
                        # active_trade = cand
                else:
                    print(f"Trade active hai - wait")
            else:
                print(f"Market band hai - {datetime.now(IST).strftime('%H:%M')}")
            time.sleep(60)  # har 1 min check karega 9:20 se 3:15 tak
        except Exception as e:
            print(f"Auto loop error: {e}")
            time.sleep(60)

# ===== RENDER WEB FIX =====
web_app = FastAPI()

@web_app.get("/")
def health_check():
    return {"status": "V24 Bot LIVE - 9:20 to 3:15 Active", "time": str(datetime.now(IST))}

if __name__ == "__main__":
    threading.Thread(target=auto_loop, daemon=True).start()
    threading.Thread(target=run_bot, daemon=True).start()
    uvicorn.run(web_app, host="0.0.0.0", port=10000)
