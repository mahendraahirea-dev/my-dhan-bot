import os, time, threading, requests, telebot
from datetime import datetime, time as dtime, timezone, timedelta
from flask import Flask

app = Flask(__name__)
@app.route('/')
def home(): return "Dhan Bot LIVE - No Premium Needed"
def run_flask():
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
threading.Thread(target=run_flask, daemon=True).start()

CLIENT_ID = (os.getenv("CLIENT_ID") or "").strip()
ACCESS_TOKEN = (os.getenv("ACCESS_TOKEN") or "").strip()
BOT_TOKEN = (os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or "").strip()
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
HEADERS = {"access-token": ACCESS_TOKEN,"client-id": CLIENT_ID,"Content-Type": "application/json"}
IST = timezone(timedelta(hours=5, minutes=30))
STATE_FILE = "/tmp/trade_state.txt"

def get_state():
    try:
        today = datetime.now(IST).strftime("%Y-%m-%d")
        if not os.path.exists(STATE_FILE): return {"date": today, "done": False, "pnl": 0}
        with open(STATE_FILE, "r") as f:
            d, done, pnl = f.read().strip().split(",")
            if d != today: return {"date": today, "done": False, "pnl": 0}
            return {"date": d, "done": done == "True", "pnl": float(pnl)}
    except: return {"date": datetime.now(IST).strftime("%Y-%m-%d"), "done": False, "pnl": 0}

def set_state(done, pnl=0):
    try:
        today = datetime.now(IST).strftime("%Y-%m-%d")
        with open(STATE_FILE, "w") as f: f.write(f"{today},{done},{pnl}")
    except: pass

# ===== DHAN + FREE FALLBACK =====
def get_free_price():
    # Yahoo free - no token needed
    prices = {}
    symbols = {"NIFTY": "%5ENSEI", "BANK": "%5ENSEBANK", "SENSEX": "%5EBSESN", "VIX": "%5EINDIAVIX", "REL": "RELIANCE.NS"}
    for k, sym in symbols.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{sym}?interval=1d"
            r = requests.get(url, headers={"User-Agent":"Mozilla/5.0"}, timeout=10)
            price = r.json()['chart']['result'][0]['meta']['regularMarketPrice']
            prices[k] = price
        except: prices[k] = None
    return prices

def get_ltp_all():
    # 1. Try Dhan first
    try:
        payload = {"NSE_EQ": [13, 25, 2885, 27],"BSE_EQ": [51],"NSE_FNO": []}
        r = requests.post("https://api.dhan.co/v2/marketfeed/ltp", json=payload, headers=HEADERS, timeout=8)
        js = r.json()
        if r.status_code == 200 and "data" in js:
            data = js.get("data", {})
            nse = data.get("NSE_EQ", {}); bse = data.get("BSE_EQ", {})
            dhan_data = {"NIFTY": nse.get("13", {}).get("last_price"),"BANK": nse.get("25", {}).get("last_price"),"REL": nse.get("2885", {}).get("last_price"),"VIX": nse.get("27", {}).get("last_price"),"SENSEX": bse.get("51", {}).get("last_price")}
            # If Dhan gives data, use it
            if dhan_data.get("NIFTY"): return dhan_data
    except Exception as e: print(f"Dhan Fail: {e}")
    
    # 2. If Dhan fails or None -> Free
    print("Using FREE Yahoo Price - No 499 Needed")
    return get_free_price()

def get_atm_strike(price, step=50):
    if not price: return None
    return int(round(price / step) * step)

def check_filters(d):
    now = datetime.now(IST)
    curr_time = now.time()
    f = {}
    f["TIME"] = dtime(9,45) <= curr_time <= dtime(15,0) # Extended to 3 PM
    vix = d.get("VIX") or 0
    f["VIX"] = vix < 25 and vix > 0 # Loosened for free data
    f["NIFTY"] = d.get("NIFTY") is not None
    f["BANK"] = d.get("BANK") is not None
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
    atm = get_atm_strike(d.get("NIFTY"), 50) if d.get("NIFTY") else None
    if state["done"]:
        bot.send_message(m.chat.id, f"🔒 1 Entry Done - NIFTY: {d.get('NIFTY')}")
        return
    status = "✅ TRADE ON" if all_ok else "🚫 NO TRADE"
    source = "FREE" if d.get("NIFTY") and d.get("NIFTY") % 1 != 0 else "DHAN"
    msg = f"📊 DHAN LIVE - NO PREMIUM ({source})\nNIFTY: {d.get('NIFTY')}\nBANK: {d.get('BANK')}\nSENSEX: {d.get('SENSEX')}\nREL: {d.get('REL')}\nVIX: {d.get('VIX')}\nATM: {atm}\n{format_filters(filters)}\nSTATUS: {status}\n/ce /pe /status"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['ce','pe','all','done','status','reset'])
def handle_others(m):
    cmd = m.text.lower()
    d = get_ltp_all()
    if "done" in cmd: set_state(True,0); bot.send_message(m.chat.id, "🔒 Lock Zali"); return
    if "reset" in cmd: set_state(False,0); bot.send_message(m.chat.id, "✅ Reset"); return
    if "status" in cmd:
        s=get_state(); bot.send_message(m.chat.id, f"Source:FREE Price\nDate:{s['date']} Done:{s['done']}\nNIFTY:{d.get('NIFTY')} BANK:{d.get('BANK')} VIX:{d.get('VIX')}"); return
    bot.send_message(m.chat.id, f"NIFTY:{d.get('NIFTY')} BANK:{d.get('BANK')} VIX:{d.get('VIX')}")

@bot.message_handler(func=lambda m: True)
def handle_any(m): bot.send_message(m.chat.id, "/start /ce /pe /all /done")

print("Bot Started - NO PREMIUM MODE")
try: bot.remove_webhook(); time.sleep(1); bot.delete_webhook(drop_pending_updates=True); time.sleep(1)
except: pass
bot.infinity_polling(timeout=60, long_polling_timeout=60, skip_pending=True)
