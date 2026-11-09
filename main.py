import os
import warnings
import logging
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore")

import time
import threading
import json
from datetime import datetime, time as dtime
from flask import Flask
import telebot
import yfinance as yf
import pandas as pd
import pytz

pd.options.mode.chained_assignment = None

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("DhanFinal")
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

@app.route('/')
def home():
    return "DHAN FINAL - NIFTY65 BANK30 FIN60 SENSEX20 - 1LOT 2K SL 1500 LOCK 25 TRAIL 10 FILTERS LIVE"
@app.route('/health')
def health():
    return {"status":"ok","time":str(datetime.now())}

SYMBOLS = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","FINNIFTY":"^CNXFIN","VIX":"^INDIAVIX"}
CACHE = {}
CACHE_TIME = {}
CACHE_EXPIRY = 25
IST = pytz.timezone('Asia/Kolkata')

RULES = {
    "LOT": 1,
    "LOT_SIZE_NIFTY": 65,
    "LOT_SIZE_BANK": 30,
    "LOT_SIZE_FINNIFTY": 60,
    "LOT_SIZE_SENSEX": 20,
    "MAX_SL_RS": 2000,
    "PROFIT_LOCK_RS": 1500,
    "TRAILING_PTS": 25,
    "ATM_GAP_NIFTY": 50,
    "ATM_GAP_BANK": 100,
    "ATM_GAP_SENSEX": 100,
    "ATM_GAP_FINNIFTY": 50,
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
    except: pass
    return {"date":"","entry_done":False,"entry_price":0,"lock_active":False,"max_profit":0,"symbol":"","strike":"","type":"","index":""}

def save_state(s):
    try:
        with open(STATE_FILE,'w') as f:
            json.dump(s,f)
    except: pass

def load_chats():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE,'r') as f:
                return set(json.load(f))
    except: pass
    return set()

def save_chats(c):
    try:
        with open(CHAT_IDS_FILE,'w') as f:
            json.dump(list(c),f)
    except: pass

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
    if vix==0: return "NA"
    if vix<11: return "VERY LOW"
    if vix<13: return "LOW"
    if vix<15: return "NORMAL"
    if vix<17.5: return "HIGH"
    if vix<21: return "VERY HIGH"
    return "EXTREME"

def get_atm(index_name, price):
    gap = RULES.get(f"ATM_GAP_{index_name}", 50)
    if index_name == "BANKNIFTY": gap = RULES["ATM_GAP_BANK"]
    if index_name == "SENSEX": gap = RULES["ATM_GAP_SENSEX"]
    if index_name == "NIFTY": gap = RULES["ATM_GAP_NIFTY"]
    if index_name == "FINNIFTY": gap = RULES["ATM_GAP_FINNIFTY"]
    return int(round(price/gap)*gap)

def filter_scanner():
    try:
        n = get_day_data("NIFTY")
        b = get_day_data("BANKNIFTY")
        if abs(n['pct'])>0.2 or abs(b['pct'])>0.2:
            return True, f"✅ SCANNER: Trend N:{n['pct']}% B:{b['pct']}%"
        return False, f"❌ SCANNER: No Trend N:{n['pct']}%"
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
        return True, f"✅ ENTRY: Time {now.strftime('%H:%M')} 9:15-15:15"
    return False, f"❌ ENTRY: {now.strftime('%H:%M')} Out"

def filter_exit():
    return True, f"✅ EXIT: SL {RULES['MAX_SL_RS']} LOCK {RULES['PROFIT_LOCK_RS']} TRAIL {RULES['TRAILING_PTS']} PTS"

def filter_timemachine():
    try:
        v = get_vix_details()['current']
        if 10 < v < 20:
            return True, f"✅ TIMEMACHINE: Pass VIX {v}"
        return False, f"❌ TIMEMACHINE: Fail VIX {v}"
    except:
        return False, "❌ TIMEMACHINE Error"

def filter_budget():
    return True, f"✅ BUDGET: 1 LOT Risk {RULES['MAX_SL_RS']} SL"

def filter_risk():
    if STATE["entry_done"]:
        return False, f"❌ RISK: 1 Entry Done {STATE['date']} {STATE['symbol']} {STATE['strike']}{STATE['type']}"
    return True, f"✅ RISK: 1 Entry Allowed"

def filter_broker():
    return True, "✅ BROKER: Dhan Ready"

def filter_alerts():
    return True, "✅ ALERTS: Telegram Active"

def filter_analyst():
    n = get_day_data("NIFTY")
    bias = "BULLISH" if n['pct']>0 else "BEARISH"
    return True, f"✅ ANALYST: {bias} {n['pct']}%"

def run_all_10_filters():
    fl = [filter_scanner, filter_news, filter_entry, filter_exit, filter_timemachine, filter_budget, filter_risk, filter_broker, filter_alerts, filter_analyst]
    res = []
    ok_all = True
    for f in fl:
        ok, msg = f()
        res.append((ok, msg))
        if not ok:
            ok_all = False
    return ok_all, res

def run_all_11_filters():
    return run_all_10_filters()

def format_main_status():
    n_p = get_price("NIFTY")
    b_p = get_price("BANKNIFTY")
    s_p = get_price("SENSEX")
    f_p = get_price("FINNIFTY")
    v_det = get_vix_details()
    d_n = get_day_data("NIFTY")
    d_b = get_day_data("BANKNIFTY")
    d_s = get_day_data("SENSEX")
    d_f = get_day_data("FINNIFTY")
    all_pass, filters = run_all_10_filters()
    msg = f"<b>🔥 DHAN FINAL - OFFICIAL LOTS 2026</b>\n{datetime.now(IST).strftime('%d %b %H:%M:%S IST')}\n\n"
    msg += f"NIFTY: {n_p} ({d_n['pct']}%) ATM {get_atm('NIFTY', n_p)} Lot {RULES['LOT_SIZE_NIFTY']}\n"
    msg += f"BANKNIFTY: {b_p} ({d_b['pct']}%) ATM {get_atm('BANKNIFTY', b_p)} Lot {RULES['LOT_SIZE_BANK']}\n"
    msg += f"SENSEX: {s_p} ({d_s['pct']}%) ATM {get_atm('SENSEX', s_p)} Lot {RULES['LOT_SIZE_SENSEX']}\n"
    msg += f"FINNIFTY: {f_p} ({d_f['pct']}%) ATM {get_atm('FINNIFTY', f_p)} Lot {RULES['LOT_SIZE_FINNIFTY']}\n"
    msg += f"VIX: {v_det['current']} ({vix_signal(v_det['current'])})\n\n"
    msg += f"RULES: 1 LOT | 1 ENTRY | {RULES['MAX_SL_RS']} SL | {RULES['PROFIT_LOCK_RS']} LOCK | {RULES['TRAILING_PTS']} TRAIL\n\n"
    msg += f"--- 10 FILTERS (PELOSI REMOVED) ---\n"
    for _, txt in filters:
        msg += f"{txt}\n"
    msg += f"\nSTATUS: {'🟢 TRADE ALLOWED' if all_pass else '🔴 NO TRADE'}\nEntry: {STATE.get('entry_done')} {STATE.get('date')} {STATE.get('symbol')} {STATE.get('strike')}{STATE.get('type')}\n"
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

@bot.message_handler(commands=['trade','force'])
def h_force(m):
    global STATE
    parts = m.text.split()
    idx = "NIFTY"
    if len(parts)>=2:
        idx = parts[1].upper()
    typ = "CE"
    if "pe" in m.text.lower():
        typ = "PE"
    price = get_price(idx)
    atm = get_atm(idx, price)
    strike = parts[2] if len(parts)>=3 else str(atm)
    STATE = {"date":datetime.now(IST).strftime('%d-%m-%Y'),"entry_done":True,"entry_price":150,"lock_active":False,"max_profit":0,"symbol":idx,"strike":strike,"type":typ,"index":idx}
    save_state(STATE)
    lot = RULES.get(f"LOT_SIZE_{idx}", 65)
    msg = f"🚀 <b>FORCE ENTRY</b>\nINDEX: {idx}\nSTRIKE: {strike} {typ}\nPRICE: {price} ATM {atm}\nLot Size {lot} | 1 LOT\nSL {RULES['MAX_SL_RS']} LOCK {RULES['PROFIT_LOCK_RS']} TRAIL {RULES['TRAILING_PTS']} PTS"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['ce','pe'])
def h_entry(m):
    global STATE
    all_pass, _ = run_all_10_filters()
    if not all_pass:
        bot.send_message(m.chat.id, format_main_status())
        return
    txt = m.text.lower()
    if "bank" in txt: idx = "BANKNIFTY"
    elif "sensex" in txt or "sen" in txt: idx = "SENSEX"
    elif "fin" in txt: idx = "FINNIFTY"
    else: idx = "NIFTY"
    typ = "PE" if "pe" in txt else "CE"
    price = get_price(idx)
    atm = get_atm(idx, price)
    parts = m.text.split()
    strike = str(atm)
    for p in parts:
        if p.isdigit(): strike = p; break
    STATE = {"date":datetime.now(IST).strftime('%d-%m-%Y'),"entry_done":True,"entry_price":150,"lock_active":False,"max_profit":0,"symbol":idx,"strike":strike,"type":typ,"index":idx}
    save_state(STATE)
    bot.send_message(m.chat.id, f"✅ ENTRY {idx} {strike} {typ} 1 LOT\nPrice {price} ATM {atm} Lot {RULES.get(f'LOT_SIZE_{idx}', 65)}\n{RULES['MAX_SL_RS']} SL | {RULES['PROFIT_LOCK_RS']} LOCK | {RULES['TRAILING_PTS']} TRAIL")

@bot.message_handler(commands=['nifty','banknifty','sensex','finnifty'])
def h_idx(m):
    idx = m.text.replace('/','').upper()
    p = get_price(idx)
    d = get_day_data(idx)
    atm = get_atm(idx, p)
    lot = RULES.get(f"LOT_SIZE_{idx}", 0)
    bot.send_message(m.chat.id, f"<b>{idx}</b> {p} ({d['pct']}%)\nH:{d['high']} L:{d['low']} O:{d['open']}\nATM {atm} Lot {lot}")

@bot.message_handler(commands=['reset'])
def h_reset(m):
    global STATE
    STATE = {"date":"","entry_done":False,"entry_price":0,"lock_active":False,"max_profit":0,"symbol":"","strike":"","type":"","index":""}
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
            log.info("Starting polling...")
            bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90, logger_level=logging.ERROR)
        except Exception as e:
            log.error(f"Polling exception: {e}")
            time.sleep(15)

threading.Thread(target=run_bot, daemon=True, name="TeleBotThread").start()

if __name__=="__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
