import os
from datetime import datetime, timedelta
from fastapi import FastAPI, Request

BOT_TOKEN = os.environ.get("BOT_TOKEN")
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN")

app = FastAPI()

def get_dhan_client():
    from dhanhq import dhanhq
    return dhanhq(DHAN_ACCESS_TOKEN)

def get_nifty_and_vix():
    try:
        dhan = get_dhan_client()
        data = dhan.quote_data(securities={"NSE_INDICES":[13,27]})
        idx = data.get('data',{}).get('NSE_INDICES',{}) if isinstance(data, dict) else {}
        nifty = float(idx.get(13,{}).get('last_price',0) or 24500)
        vix = float(idx.get(27,{}).get('last_price',0) or 14.5)
        return nifty, vix
    except: return 24500.0, 14.5

def get_vix_move(cv): 
    try: return round(((cv-14.0)/14.0)*100,2)
    except: return 0.0

def get_signal(nifty,vix,vm):
    atm=round(nifty/50)*50
    exp=(datetime.now()+timedelta(days=(3-datetime.now().weekday())%7 or 7)).strftime("%d-%b")
    if vix>16: return f"SELL {atm+100}CE"
    elif vix<13.5: return f"BUY {atm}CE"
    else: return f"WAIT {atm}"

# --- TELEGRAM LAZY ---
TG_APP = None
def get_tg_app():
    global TG_APP
    if TG_APP: return TG_APP
    from telegram.ext import Application, CommandHandler, ContextTypes
    from telegram import Update
    TG_APP = Application.builder().token(BOT_TOKEN).build()

    async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("🚀 BOT LIVE!\n/vix\n/live")

    async def vix_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        n,v=get_nifty_and_vix(); vm=get_vix_move(v)
        s=get_signal(n,v,vm)
        await update.message.reply_text(f"N:{n} VIX:{v} ({vm}%)\nSignal: {s}")

    async def live_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            dhan=get_dhan_client(); await update.message.reply_text(f"✅ {str(dhan.get_fund_limits())[:500]}")
        except Exception as e: await update.message.reply_text(f"Err {e}")

    TG_APP.add_handler(CommandHandler("start", start))
    TG_APP.add_handler(CommandHandler("vix", vix_cmd))
    TG_APP.add_handler(CommandHandler("live", live_cmd))
    return TG_APP

@app.get("/")
async def home():
    return {"status":"Bot Live - Fixed", "time": str(datetime.now())}

@app.post("/webhook")
async def webhook(req: Request):
    tg = get_tg_app()
    from telegram import Update
    data=await req.json()
    update=Update.de_json(data,tg.bot)
    await tg.process_update(update)
    return {"ok":True}

@app.on_event("startup")
async def startup():
    tg = get_tg_app()
    await tg.initialize(); await tg.start()
    h=os.environ.get("RENDER_EXTERNAL_HOSTNAME")
    if h:
        try: await tg.bot.set_webhook(f"https://{h}/webhook")
        except: pass
