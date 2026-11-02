import os, time, threading, logging, json
from datetime import datetime, time as dtime
from flask import Flask
import telebot, yfinance as yf, pandas as pd
import pytz

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Dhan380Final")

@app.route('/')
def home(): return "DHAN 380 FINAL - 1LOT 1ENTRY 2K SL 1500 LOCK 25 TRAIL + VIX + 11 FILTERS LIVE"
@app.route('/health')
def health(): return {"status":"ok"}

# ====== CONFIG - DAY 1 RULES ======
SYMBOLS = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","VIX":"^INDIAVIX","FINNIFTY":"^CNXFIN"}
CACHE = {}; CACHE_TIME = {}; CACHE_EXPIRY = 25
IST = pytz.timezone('Asia/Kolkata')

RULES = {
    "LOT": 1, # 1 lot
    "LOT_SIZE_NIFTY": 75,
    "LOT_SIZE_BANK": 30,
    "MAX_SL_RS": 2000, # 2k sl
    "PROFIT_LOCK_RS": 1500, # 1500 var profit lock
    "TRAILING_PTS": 25, # 25 pts trailing
    "MARKET_START": dtime(9,15),
    "MARKET_END": dtime(15,15),
    "AUTO_ENTRY_TIME": dtime(9,45)
}

STATE_FILE = "/tmp/state.json"
CHAT_IDS_FILE = "/tmp/chats.json"

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            return json.load(open(STATE_FILE))
    except: pass
    return {"date": "", "entry_done": False, "entry_price": 0, "sl": 0, "lock_active": False, "locked_profit": 0, "max_profit": 0, "symbol": "", "strike": "", "type": ""}

def save_state(s):
    try: json.dump(s, open(STATE_FILE,'w'))
    except: pass

def load_chats():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            return set(json.load(open(CHAT_IDS_FILE)))
    except: pass
    return set()

def save_chats(chats):
    try: json.dump(list(chats), open(CHAT_IDS_FILE,'w'))
    except: pass

STATE = load_state()
CHAT_IDS = load_chats()

# ===== PRICE =====
def get_hist(key, period="1d", interval="1m"):
    try: return yf.Ticker(SYMBOLS.get(key,key)).history(period=period, interval=interval, auto_adjust=True)
    except: return pd.DataFrame()

def get_price(key):
    try:
        now = time.time()
        if key in CACHE and now - CACHE_TIME.get(key,0) < CACHE_EXPIRY: return CACHE[key]
        h = get_hist(key)
        if h.empty: return CACHE.get(key,0)
        p = round(float(h['Close'].iloc[-1]),2)
        CACHE[key]=p; CACHE_TIME[key]=now
        return p
    except: return CACHE.get(key,0)

def get_day_data(key):
    try:
        h = get_hist(key, period="1d", interval="5m")
        if h.empty: return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}
        high = round(float(h['High'].max()),2); low = round(float(h['Low'].min()),2)
        op = round(float(h['Open'].iloc[0]),2); cl = round(float(h['Close'].iloc[-1]),2)
        ch = cl-op; pct = round(ch/op*100 if op else 0,2)
        return {"high":high,"low":low,"open":op,"close":cl,"change":ch,"pct":pct}
    except: return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}

# ===== VIX FULL CALCULATION =====
def get_vix(): 
    try:
        p=get_price("VIX")
        if p==0:
            h=get_hist("VIX", period="5d", interval="1d")
            if not h.empty: p=float(h['Close'].iloc[-1])
        return round(p,2)
    except: return 0

def get_vix_details():
    try:
        h=get_hist("VIX", period="10d", interval="1d")
        if h.empty: return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0,"avg5":0}
        curr=round(float(h['Close'].iloc[-1]),2); high=round(float(h['High'].iloc[-1]),2); low=round(float(h['Low'].iloc[-1]),2)
        prev=round(float(h['Close'].iloc[-2]),2) if len(h)>1 else curr; avg5=round(float(h['Close'].tail(5).mean()),2)
        return {"current":curr,"high":high,"low":low,"prev":prev,"change":round(curr-prev,2),"avg5":avg5}
    except: return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0,"avg5":0}

def vix_signal(vix):
    if vix==0: return "NA"
    if vix<11: return "VERY LOW - Selling Best"
    if vix<13: return "LOW - Range"
    if vix<15: return "NORMAL"
    if vix<17.5: return "HIGH - Big Moves"
    if vix<21: return "VERY HIGH - Scalp"
    return "EXTREME - Avoid"

# ===== CLAUDE 11 FILTERS - AS PER SCREENSHOT REPO =====
# Repo: 11 skills = scanner, news, entry, exit, timemachine, risk, budget, broker, alerts, analyst, pelosi【4050319062241097336†L18-L22】
def filter_scanner():
    # trader-scanner: Scans charts for opening-range breakouts, flags【4050319062241097336†L47-L50】
    try:
        n = get_day_data("NIFTY"); b = get_day_data("BANKNIFTY")
        if abs(n['pct'])>0.2 or abs(b['pct'])>0.2: return True, f"✅ SCANNER: Trend {n['pct']}%"
        return False, f"❌ SCANNER: No Trend {n['pct']}%"
    except: return False, "❌ SCANNER Error"

def filter_news():
    # trader-news: monitor public news and filings【4050319062241097336†L38-L41】
    # Free me news API nahi, to VIX se proxy
    vix=get_vix()
    if vix<20: return True, f"✅ NEWS: No High Impact VIX {vix}"
    return False, f"❌ NEWS: High Impact VIX {vix}"

def filter_entry():
    # trader-entry: identify entry signals【4050319062241097336†L38-L41】
    now = datetime.now(IST)
    if RULES["MARKET_START"] <= now.time() <= RULES["MARKET_END"]:
        return True, f"✅ ENTRY: Time {now.strftime('%H:%M')}"
    return False, f"❌ ENTRY: Time {now.strftime('%H:%M')} Out of 9:15-15:15"

def filter_exit():
    # trader-exit: plan exits【4050319062241097336†L38-L41】
    return True, f"✅ EXIT: SL {RULES['MAX_SL_RS']} Profit Lock {RULES['PROFIT_LOCK_RS']} Trail {RULES['TRAILING_PTS']}"

def filter_timemachine():
    # trader-timemachine: replay trade
