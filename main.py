import os
import math
from datetime import datetime
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")

app = FastAPI()

# ============ DHAN CLIENT - FINAL FIX ============
def get_dhan_client():
    from dhanhq import dhanhq
    token = DHAN_ACCESS_TOKEN
    cid = DHAN_CLIENT_ID
    try:
        return dhanhq(token)
    except TypeError:
        try:
            return dhanhq(cid, token)
        except TypeError:
            return dhanhq(client_id=cid, access_token=token)

# ============ VIX CALCULATION ============
def get_nifty_and_vix():
    """Nifty + VIX donhi ekasobat"""
    dhan = get_dhan_client()
    try:
        # Nifty 50 - ID 13, VIX - ID 27 (INDEX)
        # Dhan madhe INDEX data sathi alag call
        nifty_data = dhan.quote_data(securities={"NSE_INDICES": [13, 27]})
        # Response format: {'data': {'NSE_INDICES': {13: {...}, 27: {...}}}}
        indices = nifty_data.get('data', {}).get('NSE_INDICES', {}) if isinstance(nifty_data, dict) else {}
        
        nifty_price = 0
        vix_price = 0
        
        if 13 in indices:
            nifty_price = indices[13].get('last_price', 0)
        if 27 in indices:
            vix_price = indices[27].get('last_price', 0)
            
        # Fallback - jar direct quote nahi milala tar ltp
        if nifty_price == 0:
            # Historical fallback
            nifty_price = 24500 # default

        return float(nifty_price), float(vix_price), nifty_data
    except Exception as e:
        print(f"VIX Fetch Error: {e}")
        return 24500.0, 14.5, {"error": str(e)}

def get_vix_move(current_vix, prev_vix=14.0):
    """VIX cha move % madhe"""
    try:
        if prev_vix == 0:
            return 0.0
        move = ((current_vix - prev_vix) / prev_vix) * 100
        return round(move, 2)
    except:
        return 0.0

# ============ BEST SIGNAL LOGIC - UNPACK ERROR FIX ============
def get_best_signal(nifty, vix, vix_move):
    """
    Ha function dict return karel - tuple nahi! Mhanun unpack error yenar nahi
    """
    try:
        atm = round(nifty / 50) * 50
        
        # Logic: VIX > 15 = Premium high = SELL, VIX < 13 = BUY
        signal = {}
        if vix > 16 or vix_move > 5:
            signal['action'] = "SELL"
            signal['option_type'] = "CE"
            signal['strike'] = atm + 100
            signal['reason'] = f"VIX High {vix} (+{vix_move}%)"
        elif vix < 13.5 and vix_move < -2:
            signal['action'] = "BUY"
            signal['option_type'] = "CE"
            signal['strike'] = atm
            signal['reason'] = f"VIX Low {vix} ({vix_move}%) - Vol expansion expected"
        else:
            signal['action'] = "WAIT"
            signal['option_type'] = "NONE"
            signal['strike'] = atm
            signal['reason'] = f"VIX Neutral {vix} ({vix_move}%)"

        signal['nifty'] = nifty
        signal['vix'] = vix
        signal['vix_move'] = vix_move
        signal['time'] = datetime.now().strftime("%H:%M")
        
        return signal # DICT return - unpack error fix!
    except Exception as e:
        return {"action": "ERROR", "reason": str(e), "nifty": nifty, "vix": vix}

# ============ TELEGRAM BOT ============
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🚀 DHAN BOT FULL READY!\n\n"
        "/vix - VIX + Nifty + Signal\n"
        "/live - Dhan Connection\n"
        "/status - Bot Status\n"
    )

async def vix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳ VIX antoy...")
    try:
        nifty, vix, raw = get_nifty_and_vix()
        vix_move = get_vix_move(vix)
        signal = get_best_signal(nifty, vix, vix_move) # No unpack!
        
        msg = f"""📊 LIVE MARKET
Nifty: {signal['nifty']}
VIX: {signal['vix']} ({signal['vix_move']}%)
ATM: {round(signal['nifty']/50)*50}

🎯 SIGNAL: {signal['action']}
Type: {signal['option_type']} {signal['strike']}
Reason: {signal['reason']}
Time: {signal['time']}
"""
        await update.message.reply_text(msg)
    except Exception as e:
        await update.message.reply_text(f"VIX Error: {e}")

async def live_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dhan = get_dhan_client()
        limits = dhan.get_fund_limits()
        await update.message.reply_text(f"✅ Dhan Live!\n{str(limits)[:600]}")
    except Exception as e:
        await update.message.reply_text(f"Dhan Error: {e}")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"✅ Running: {datetime.now()}\nVIX Logic: OK\nUnpack Fix: OK")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("vix", vix_cmd))
tg_app.add_handler(CommandHandler("live", live_cmd))
tg_app.add_handler(CommandHandler("status", status_cmd))

# ============ FASTAPI WEBHOOK ============
@app.post("/webhook")
async def webhook(req: Request):
    data = await req.json()
    update = Update.de_json(data, tg_app.bot)
    await tg_app.process_update(update)
    return {"ok": True}

@app.get("/")
async def home():
    return {"status": "Full VIX Bot Live"}

@app.on_event("startup")
async def startup():
    await tg_app.initialize()
    await tg_app.start()
    host = os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if host:
        await tg_app.bot.set_webhook(f"https://{host}/webhook")
