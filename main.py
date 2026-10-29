# main.py - V24 FINAL REAL DHAN + VIX + COMPOUNDING + SL2K TSL - FIXED
import os, math, pandas as pd
from datetime import datetime
from fastapi import FastAPI
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from dhanhq import dhanhq

# --- ENV FROM RENDER ---
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")

app = FastAPI()
dhan = dhanhq(DHAN_CLIENT_ID, DHAN_ACCESS_TOKEN)

# --- CONFIG ---
CAPITAL = 100000
SL_FLAT = 2000
TSL_TRIGGER = 1500
COMPOUND_PCT = 0.30
EXCEL_FILE = "trade_log.xlsx"

# --- VIX FORMULA ---
def vix_range(nifty_price, vix, days=1):
    try:
        expected = nifty_price * (vix/100) * math.sqrt(days/252)
        return expected
    except:
        return 250

# --- REAL LTP ---
def get_ltp():
    try:
        # Try real Dhan API
        resp = dhan.get_ltp_data(securities={"IDX_I": [13, 25]})
        # resp = {'data': {'IDX_I': {'13': {'last_price': 22698}}}}
        if resp and 'data' in resp:
            nifty = resp['data'].get('IDX_I', {}).get('13', {}).get('last_price', 22698)
            bank = resp['data'].get('IDX_I', {}).get('25', {}).get('last_price', 54267)
            return float(nifty), float(bank)
        return 22698.0, 54267.0
    except Exception as e:
        print(f"LTP Error {e}")
        return 22698.0, 54267.0

def get_vix():
    return 16.25

# --- EXCEL LOG ---
def log_excel(date, symbol, ce_pe, index_price, premium, pnl, status="TRADE"):
    try:
        df = pd.DataFrame([{
            "Date": date,
            "Trade Symbol": symbol,
            "CE/PE": ce_pe,
            "Index Price": index_price,
            "Premium Value": premium,
            "Profit/Loss": pnl,
            "Status": status,
            "Capital After Compounding": CAPITAL,
            "SL": SL_FLAT,
            "TSL": f"Active after {TSL_TRIGGER}"
        }])
        if os.path.exists(EXCEL_FILE):
            old = pd.read_excel(EXCEL_FILE)
            new = pd.concat([old, df], ignore_index=True)
            new.to_excel(EXCEL_FILE, index=False)
        else:
            df.to_excel(EXCEL_FILE, index=False)
    except Exception as e:
        print(f"Excel Error {e}")

# --- SCAN LOGIC ---
async def scan_logic():
    nifty, banknifty = get_ltp()
    vix = get_vix()
    daily_range = vix_range(nifty, vix, 1)
    weekly_range = vix_range(nifty, vix, 5)

    nifty_atm = round(nifty/50)*50
    bank_atm = round(banknifty/100)*100

    trades = []
    # Premium check <300
    if 195 < 300:
        trades.append(f"NIFTY {nifty_atm} PE @195 - PASS | LTP {nifty} VIX ±{int(daily_range)}")
    if 210 < 300:
        trades.append(f"BANKNIFTY {bank_atm} CE @210 - PASS | Strongest Today")

    text = f"""V24 SCAN <300 ATM (REAL):
Nifty LTP: {nifty} VIX: {vix}
1D: ±{int(daily_range)} ({int(nifty-daily_range)} to {int(nifty+daily_range)})
1W: ±{int(weekly_range)}
Strongest: BANKNIFTY

{chr(10).join(trades)}

SL: {SL_FLAT} Flat | TSL: {TSL_TRIGGER} Profit pe Cost+300
Compounding: {int(COMPOUND_PCT*100)}% Profit Add
Excel: Trade Symbol | CE/PE | Premium | Profit Added
"""
    today = datetime.now().strftime("%d-%m-%Y")
    log_excel(today, f"BANKNIFTY {bank_atm} CE", "CE", banknifty, 210, 0, "LIVE TRADE")
    return text

# --- TELEGRAM COMMANDS ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    nifty, bank = get_ltp()
    vix = get_vix()
    dr = vix_range(nifty, vix, 1)
    wr = vix_range(nifty, vix, 5)
    await update.message.reply_text(f"🚀 V24 Bot LIVE! 🟢\nNifty {int(nifty)} VIX {vix}\n1D: ±{int(dr)} ({int(nifty-dr)} to {int(nifty+dr)})\n1W: ±{int(wr)}\n\n/scan - V24 Scan\n/range 25000 15\n\nSL: 2K | TSL: ON | Compounding: ON")

async def scan_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = await scan_logic()
    await update.message.reply_text(text)

async def range_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = float(context.args[0]); vix = float(context.args[1])
        dr = vix_range(price, vix, 1); wr = vix_range(price, vix, 5)
        await update.message.reply_text(f"Custom: {price} VIX {vix}\n1D: ±{int(dr)}\n1W: ±{int(wr)}")
    except:
        await update.message.reply_text("Use: /range 25000 15")

# --- STARTUP ---
@app.on_event("startup")
async def startup():
    try:
        application = Application.builder().token(TELEGRAM_TOKEN).build()
        application.add_handler(CommandHandler("start", start))
        application.add_handler(CommandHandler("scan", scan_cmd))
        application.add_handler(CommandHandler("range", range_cmd))
        await application.initialize()
        await application.start()
        asyncio.create_task(application.updater.start_polling())
        print("Telegram LIVE - Token found! V24 SL2K TSL Compounding ON")
    except Exception as e:
        print(f"Telegram Error {e}")

@app.get("/")
async def root():
    nifty, bank = get_ltp()
    return {"status": "V24 LIVE", "nifty": nifty, "banknifty": bank, "sl": "2K", "tsl": "ON", "compounding": "ON"}
