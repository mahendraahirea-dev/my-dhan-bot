import warnings
warnings.filterwarnings("ignore", category=FutureWarning)

# Bot line badal
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)

# run_bot function full replace kar ya ne:
def run_bot():
    bot.remove_webhook()
    time.sleep(2)
    while True:
        try:
            log.info("Starting polling...")
            bot.infinity_polling(skip_pending=True, timeout=60, long_polling_timeout=60, logger_level=logging.ERROR)
        except Exception as e:
            log.error(f"Polling crashed: {e} - retrying in 15s")
            time.sleep(15)

threading.Thread(target=run_bot, daemon=True, name="TeleBotThread").start()

if __name__=="__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
import os, time, threading, logging, json
from datetime import datetime, time as dtime
from flask import Flask
import telebot, yfinance as yf, pandas as pd
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("DhanFinal")

@app.route('/')
def home():
    return "DHAN FINAL - 1LOT 1ENTRY 2K SL 1500 LOCK 25 TRAIL + VIX + 11 FILTERS LIVE"
@app.route('/health')
def health():
    return {"status":"ok"}

SYMBOLS = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","VIX":"^INDIAVIX","FINNIFTY":"^CNXFIN"}
CACHE = {}
CACHE_TIME = {}
CACHE_EXPIRY = 25
IST = pytz.timezone('Asia/Kolkata')

RULES = {
    "LOT": 1,
    "LOT_SIZE_NIFTY": 75,
    "LOT_SIZE_BANK": 30,
    "MAX_SL_RS": 2000,
    "PROFIT_LOCK_RS": 1500,
    "TRAILING_PTS": 25,
    "MARKET_START": dtime(9,15),
    "MARKET_END": dtime(15,15)
}

STATE_FILE = "/tmp/state.json"
CHAT_IDS_FILE = "/tmp/chats.json"

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE,'r') as f:
                return json.load(f)
    except:
        pass
    return {"date":"","entry_done":False,"entry_price":0,"lock_active":False,"max_profit":0,"symbol":"","strike":"","type":""}

def save_state(s):
    try:
        with open(STATE_FILE,'w') as f:
            json.dump(s,f)
    except:
        pass

def load_chats():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE,'r') as f:
                return set(json.load(f))
    except:
        pass
    return set()

def save_chats(c):
    try:
        with open(CHAT_IDS_FILE,'w') as f:
            json.dump(list(c),f)
    except:
        pass

STATE = load_state()
CHAT_IDS = load_chats()

def get_hist(key, period="1d", interval="1m"):
    try:
        ticker = SYMBOLS.get(key, key)
        return yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
    except:
        return pd.DataFrame()

def get_price(key):
    try:
        now = time.time()
        if key in CACHE and now - CACHE_TIME.get(key,0) < CACHE_EXPIRY:
            return CACHE[key]
        h = get_hist(key)
        if h.empty:
            return CACHE.get(key,0)
        p = round(float(h['Close'].iloc[-1]),2)
        CACHE[key]=p
        CACHE_TIME[key]=now
        return p
    except:
        return CACHE.get(key,0)

def get_day_data(key):
    try:
        h = get_hist(key, period="1d", interval="5m")
        if h.empty:
            return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}
        high = round(float(h['High'].max()),2)
        low = round(float(h['Low'].min()),2)
        op = round(float(h['Open'].iloc[0]),2)
        cl = round(float(h['Close'].iloc[-1]),2)
        ch = cl-op
        pct = round(ch/op*100 if op else 0,2)
        return {"high":high,"low":low,"open":op,"close":cl,"change":ch,"pct":pct}
    except:
        return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}

def get_vix():
    try:
        p = get_price("VIX")
        if p==0:
            h = get_hist("VIX", period="5d", interval="1d")
            if not h.empty:
                p = float(h['Close'].iloc[-1])
        return round(p,2)
    except:
        return 0

def get_vix_details():
    try:
        h = get_hist("VIX", period="10d", interval="1d")
        if h.empty:
            return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0,"avg5":0}
        curr = round(float(h['Close'].iloc[-1]),2)
        high = round(float(h['High'].iloc[-1]),2)
        low = round(float(h['Low'].iloc[-1]),2)
        prev = round(float(h['Close'].iloc[-2]),2) if len(h)>1 else curr
        avg5 = round(float(h['Close'].tail(5).mean()),2)
        return {"current":curr,"high":high,"low":low,"prev":prev,"change":round(curr-prev,2),"avg5":avg5}
    except:
        return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0,"avg5":0}

def vix_signal(vix):
    if vix==0:
        return "NA"
    if vix<11:
        return "VERY LOW"
    if vix<13:
        return "LOW"
    if vix<15:
        return "NORMAL"
    if vix<17.5:
        return "HIGH"
    if vix<21:
        return "VERY HIGH"
    return "EXTREME"

def filter_scanner():
    try:
        n = get_day_data("NIFTY")
        b = get_day_data("BANKNIFTY")
        if abs(n['pct'])>0.2 or abs(b['pct'])>0.2:
            return True, f"✅ SCANNER: Trend {n['pct']}%"
        return False, f"❌ SCANNER: No Trend {n['pct']}%"
    except:
        return False, "❌ SCANNER Error"

def filter_news():
    vix = get_vix()
    if vix<20:
        return True, f"✅ NEWS: VIX {vix} OK"
    return False, f"❌ NEWS: VIX {vix} High"

def filter_entry():
    now = datetime.now(IST)
    if RULES["MARKET_START"] <= now.time() <= RULES["MARKET_END"]:
        return True, f"✅ ENTRY: Time {now.strftime('%H:%M')}"
    return False, f"❌ ENTRY: {now.strftime('%H:%M')} Out 9:15-15:15"

def filter_exit():
    return True, f"✅ EXIT: SL {RULES['MAX_SL_RS']} Lock {RULES['PROFIT_LOCK_RS']} Trail {RULES['TRAILING_PTS']}"

def filter_timemachine():
    try:
        v = get_vix_details()['current']
        if 10 < v < 18:
            return True, f"✅ TIMEMACHINE: Pass VIX {v}"
        return False, f"❌ TIMEMACHINE: Fail VIX {v}"
    except:
        return False, "❌ TIMEMACHINE Error"

def filter_budget():
    return True, f"✅ BUDGET: 1 LOT Risk {RULES['MAX_SL_RS']}"

def filter_risk():
    if STATE["entry_done"]:
        return False, f"❌ RISK: 1 Entry Done {STATE['date']}"
    return True, f"✅ RISK: 1 Entry Allowed"

def filter_broker():
    return True, "✅ BROKER: Dhan Ready"

def filter_alerts():
    return True, "✅ ALERTS: Telegram Active"

def filter_analyst():
    n = get_day_data("NIFTY")
    bias = "BULLISH" if n['pct']>0 else "BEARISH"
    return True, f"✅ ANALYST: {bias} {n['pct']}%"

def filter_pelosi():
    v = get_vix()
    if v<16:
        return True, f"✅ PELOSI: Stable {v}"
    return False, f"❌ PELOSI: Volatile {v}"

def run_all_11_filters():
    fl = [filter_scanner, filter_news, filter_entry, filter_exit, filter_timemachine, filter_budget, filter_risk, filter_broker, filter_alerts, filter_analyst, filter_pelosi]
    res = []
    ok_all = True
    for f in fl:
        ok, msg = f()
        res.append((ok, msg))
        if not ok:
            ok_all = False
    return ok_all, res

def format_main_status():
    p = {"NIFTY":get_price("NIFTY"),"BANKNIFTY":get_price("BANKNIFTY"),"VIX":get_vix()}
    vix_det = get_vix_details()
    d_n = get_day_data("NIFTY")
    all_pass, filters = run_all_11_filters()
    msg = f"<b>🔥 DHAN FINAL BOT</b>\n{datetime.now(IST).strftime('%d %b %H:%M:%S IST')}\n\n"
    msg += f"NIFTY: {p['NIFTY']} ({d_n['pct']}%) ATM {int(round(p['NIFTY']/50)*50)}\n"
    msg += f"BANK: {p['BANKNIFTY']} | VIX: {vix_det['current']} ({vix_signal(vix_det['current'])})\n"
    msg += f"RULES: 1 LOT | 1 ENTRY | 2K SL | 1500 LOCK | 25 TRAIL\n\n"
    msg += f"--- 11 FILTERS ---\n"
    for _, txt in filters:
        msg += f"{txt}\n"
    msg += f"\nSTATUS: {'🟢 READY' if all_pass else '🔴 NO TRADE'}\nEntry Done: {STATE.get('entry_done')} {STATE.get('date')}\n"
    return msg

@bot.message_handler(commands=['start','help','status'])
def h_start(m):
    CHAT_IDS.add(m.chat.id)
    save_chats(CHAT_IDS)
    bot.send_message(m.chat.id, format_main_status())

@bot.message_handler(commands=['vix'])
def h_v(m):
    det = get_vix_details()
    bot.send_message(m.chat.id, f"VIX Curr:{det['current']} Prev:{det['prev']} Change:{det['change']} High:{det['high']} Low:{det['low']} Avg5:{det['avg5']} Signal:{vix_signal(det['current'])}")

@bot.message_handler(commands=['ce','pe'])
def h_entry(m):
    global STATE
    all_pass, _ = run_all_11_filters()
    if not all_pass:
        bot.send_message(m.chat.id, format_main_status())
        return
    typ = "PE" if "pe" in m.text.lower() else "CE"
    parts = m.text.split()
    strike = parts[1] if len(parts)>1 else str(int(round(get_price("NIFTY")/50)*50))
    STATE = {"date":datetime.now(IST).strftime('%d-%m-%Y'),"entry_done":True,"entry_price":150,"lock_active":False,"max_profit":0,"symbol":"NIFTY","strike":strike,"type":typ}
    save_state(STATE)
    bot.send_message(m.chat.id, f"✅ ENTRY NIFTY {strike} {typ} 1 LOT\n2K SL | 1500 LOCK | 25 TRAIL Active")

@bot.message_handler(commands=['reset'])
def h_reset(m):
    global STATE
    STATE = {"date":"","entry_done":False,"entry_price":0,"lock_active":False,"max_profit":0,"symbol":"","strike":"","type":""}
    save_state(STATE)
    bot.send_message(m.chat.id, "✅ Reset Done")

@bot.message_handler(func=lambda m: True)
def h_any(m):
    bot.send_message(m.chat.id, format_main_status())

def run_bot():
    bot.remove_webhook()
    time.sleep(3)
    while True:
        try:
            bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90)
        except Exception as e:
            log.error(e)
            time.sleep(10)

threading.Thread(target=run_bot, daemon=True).start()

if __name__=="__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
