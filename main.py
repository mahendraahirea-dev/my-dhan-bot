import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")

app = FastAPI()

# --- DHAN CLIENT - FINAL FIX ---
def get_dhan_client():
    from dhanhq import dhanhq
    t=DHAN_ACCESS_TOKEN; c=DHAN_CLIENT_ID
    try: return dhanhq(t)
    except TypeError:
        try: return dhanhq(c,t)
        except: return dhanhq(client_id=c, access_token=t)

# --- VIX + NIFTY ---
def get_nifty_and_vix():
    dhan = get_dhan_client()
    try:
        data = dhan.quote_data(securities={"NSE_INDICES": [13,27]})
        idx = data.get('data',{}).get('NSE_INDICES',{}) if isinstance(data,dict) else {}
        nifty = float(idx.get(13,{}).get('last_price',0) or 24500)
        vix = float(idx.get(27,{}).get('last_price',0) or 14.5)
        return nifty, vix
    except: return 24500.0, 14.5

def get_vix_move(cv, pv=14.0):
    # FLOAT return - unpack karaycha nahi!
    try: return round(((cv-pv)/pv)*100,2)
    except: return 0.0

def get_next_expiry():
    today=datetime.now()
    days_ahead = 3 - today.weekday()
    if days_ahead <=0: days_ahead+=7
    return (today+timedelta(days=days_ahead)).strftime("%d-%b")

def get_best_signal(nifty, vix, vix_move):
    atm = round(nifty/50)*50
    expiry = get_next_expiry()
    # NO UNPACK - DICT RETURN
    if vix>16 or vix_move>5:
        return {"action":"SELL","type":"CE","strike":atm+100,"atm":atm,"expiry":expiry,"reason":f"VIX High {vix} ({vix_move}%)"}
    elif vix<13.5 and vix_move<-2:
        return {"action":"BUY","type":"CE","strike":atm,"atm":atm,"expiry":expiry,"reason":f"VIX Low {vix} ({vix_move}%)"}
    else:
        return {"action":"WAIT","type":"NONE","strike":atm,"atm":atm,"expiry":expiry,"reason":f"VIX Neutral {vix} ({vix_move}%)"}

# --- TELEGRAM ---
tg_app = Application.builder().token(BOT_TOKEN).build()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🚀 DHAN BOT DEPLOYED!\n/vix - Full Signal\n/live - Dhan\n/positions - P&L")

async def vix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("⏳...")
    nifty,vix = get_nifty_and_vix()
    vm = get_vix_move(vix)
    s = get_best_signal(nifty,vix,vm)
    msg=f"📊 Nifty:{nifty} ATM:{s['atm']}\nVIX:{vix} ({vm}%)\nExp:{s['expiry']}\n\n🎯 {s['action']} {s['type']} {s['strike']}\n{s['reason']}"
    await update.message.reply_text(msg)

async def live_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dhan=get_dhan_client(); lim=dhan.get_fund_limits()
        await update.message.reply_text(f"✅ DHAN OK\n{str(lim)[:500]}")
    except Exception as e: await update.message.reply_text(f"Err {e}")

async def positions_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        dhan=get_dhan_client(); pos=dhan.get_positions()
        await update.message.reply_text(f"📦 {str(pos)[:800]}")
    except Exception as e: await update.message.reply_text(f"Err {e}")

async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"✅ Live {datetime.now()}")

tg_app.add_handler(CommandHandler("start", start))
tg_app.add_handler(CommandHandler("vix", vix_cmd))
tg_app.add_handler(CommandHandler("live", live_cmd))
tg_app.add_handler(CommandHandler("positions", positions_cmd))
tg_app.add_handler(CommandHandler("status", status_cmd))

# --- WEBHOOK - NO FLASK ---
@app.get("/")
async def home():
    return {"status":"Bot Live - Deploy OK"} # Simple - kahi call nahi!

@app.post("/webhook")
async def webhook(req: Request):
    data=await req.json()
    update=Update.de_json(data,tg_app.bot)
    await tg_app.process_update(update)
    return {"ok":True}

@app.on_event("startup")
async def startup():
    await tg_app.initialize(); await tg_app.start()
    h=os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if h: await tg_app.bot.set_webhook(f"https://{h}/webhook")
