import os
import time
import threading
import requests
import telebot
from datetime import datetime, time as dtime, timezone, timedelta
from flask import Flask

# ========= RENDER PORT FIX - NO MORE No open ports =========
app = Flask(__name__)
@app.route('/')
def home():
    return "Dhan Bot is Live - FINAL"

def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)

threading.Thread(target=run_flask, daemon=True).start()
# =============================================================

CLIENT_ID = (os.getenv("CLIENT_ID") or os.getenv("CLIENTID") or "").strip()
ACCESS_TOKEN = (os.getenv("ACCESS_TOKEN") or os.getenv("ACCESSTOKEN") or "").strip()
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or "").strip()

if not BOT_TOKEN:
    raise Exception("BOT_TOKEN missing in Render ENV")

bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
HEADERS = {"access-token": ACCESS_TOKEN,"client-id": CLIENT_ID,"Content-Type": "application/json"}

IST = timezone(timedelta(hours=5, minutes=30))
STATE_FILE = "/tmp/trade_state.txt"

def get_state():
    try:
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if not os.path.exists(STATE_FILE):
            return {"date": today, "done": False, "pnl": 0}
        with open(STATE_FILE, "r") as f:
            data = f.read().strip().split(",")
            d, done, pnl = data[0], data[1], data[2]
            if d != today:
                return {"date": today, "done": False, "pnl": 0}
            return {"date": d, "done": done == "True", "pnl": float(pnl)}
    except:
        return {"date": datetime.now(IST).strftime("%Y-%m-%d"), "done": False, "pnl": 0}

def set_state(done, pnl=0):
    try:
        today = datetime.now(IST).strftime("%Y-%m-%d")
        with open(STATE_FILE, "w") as f:
            f.write(f"{today},{done},{pnl}")
    except: pass

def get_ltp_all():
    try:
        payload = {"NSE_EQ": [13, 25, 2885, 27],"BSE_EQ": [51],"NSE_FNO": []}
        r = requests.post("https://api.dhan.co/v2/marketfeed/ltp", json=payload, headers=HEADERS, timeout=10)
        js = r.json()
        data = js.get("data", {})
        nse = data.get("NSE_EQ", {})
        bse = data.get("BSE_EQ", {})
        return {"NIFTY": nse.get("13", {}).get("last_price"),"BANK": nse.get("25", {}).get("last_price"),"REL": nse.get("2885", {}).get("last_price"),"VIX": nse.get("27", {}).get("last_price"),"SENSEX": bse.get("51", {}).get("last_price")}
    except Exception as e:
        print(f"LTP Error: {e}")
        return {"NIFTY": None, "BANK": None, "SENSEX": None, "REL": None, "VIX": None}

def get_atm_strike(price, step=50):
    if not price: return None
    return int(round(price / step) * step)

def check_filters(d):
    now = datetime.now(IST)
    curr_time = now.time()
    f = {}
    f["TIME"] = dtime(9,45) <= curr_time <= dtime(11,30)
    vix = d.get("VIX") or 999
    f["VIX"] = vix < 16 and vix > 0
    f["NIFTY"] = d.get("NIFTY") is not None
    f["BANK"] = d.get("BANK") is not None
    f["SENSEX"] = d.get("SENSEX") is not None
    f["RELIANCE"] = d.get("REL") is not None
    f["ONE_ENTRY"] = not get_state()["done"]
    all_ok = all([f["TIME"], f["VIX"], f["NIFTY"], f["ONE_ENTRY"]])
    return f, all_ok

def format_filters(f):
    txt = ""
    for k,v in f.items():
        txt += f"{'✅' if v else '❌'} {k}  "
        if k in ["TIME","VIX","ONE_ENTRY"]: txt += "\n"
    return txt

@bot.message_handler(commands=['start'])
def handle_start(m):
    d = get_ltp_all()
    state = get_state()
    filters, all_ok = check_filters(d)
    nifty = d.get("NIFTY")
    atm = get_atm_strike(nifty, 50) if nifty else None
    if state["done"]:
        bot.send_message(m.chat.id, f"🔒 1 Entry Done - NIFTY: {nifty}")
        return
    status = "✅ TRADE ON" if all_ok else "🚫 NO TRADE"
    msg = f"📊 DHAN LIVE - FINAL\nNIFTY: {d.get('NIFTY')}\nBANK: {d.get('BANK')}\nSENSEX: {d.get('SENSEX')}\nREL: {d.get('REL')}\nVIX: {d.get('VIX')}\nATM: {atm}\n{format_filters(filters)}\nSTATUS: {status}\n/ce /pe /done"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['ce','pe','all','done','status','reset'])
def handle_others(m):
    cmd = m.text.lower()
    d = get_ltp_all()
    if "done" in cmd:
        set_state(True,0); bot.send_message(m.chat.id, "🔒 Lock Zali"); return
    if "reset" in cmd:
        set_state(False,0); bot.send_message(m.chat.id, "✅ Reset"); return
    if "status" in cmd:
        s=get_state(); bot.send_message(m.chat.id, f"Date:{s['date']} Done:{s['done']} NIFTY:{d.get('NIFTY')}"); return
    bot.send_message(m.chat.id, f"NIFTY:{d.get('NIFTY')} BANK:{d.get('BANK')} VIX:{d.get('VIX')}")

@bot.message_handler(func=lambda m: True)
def handle_any(m):
    bot.send_message(m.chat.id, "/start /ce /pe /all /done")

print("Bot Started - FINAL NO PYTZ - FIXED")
try:
    bot.remove_webhook()
    time.sleep(1)
    bot.delete_webhook(drop_pending_updates=True)
    time.sleep(1)
except: pass

bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
