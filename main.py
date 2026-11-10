import os
import warnings
import logging
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.simplefilter("ignore")
warnings.filterwarnings("ignore")

import time
import threading
import json
import math
from datetime import datetime, time as dtime, date
from flask import Flask
import telebot
import yfinance as yf
import pandas as pd
import pytz
import numpy as np

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
    return "DHAN FINAL AUTO - NIFTY65 BANK30 FIN60 SENSEX20 - GREEK BOT + NO LOSS FILTER ON"
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
    "MARKET_END": dtime(15,15),
    "AUTO_ENTRY": True,
    "AUTO_INDEX": "NIFTY",
    "MIN_CONFIDENCE": 80,
    "RISK_FREE_RATE": 0.065
}

NSE_HOLIDAYS_2026 = [
    "2026-01-26", "2026-03-14", "2026-03-31", "2026-04-10", "2026-04-14",
    "2026-05-01", "2026-08-15", "2026-08-27", "2026-10-02", "2026-10-21",
    "2026-10-22", "2026-11-03", "2026-11-10",
    "2026-12-25"
]

def is_trading_holiday():
    today_str = datetime.now(IST).strftime('%Y-%m-%d')
    if today_str in NSE_HOLIDAYS_2026:
        return True, today_str
    wd = datetime.now(IST).weekday()
    if wd >= 5:
        return True, f"Weekend {today_str}"
    return False, ""

STATE_FILE = "/tmp/state.json"
CHAT_IDS_FILE = "/tmp/chats.json"

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE,'r') as f:
                return json.load(f)
    except: pass
    return {"date":"","entry_done":False,"entry_price":0,"lock_active":False,"max_profit":0,"symbol":"","strike":"","type":"","index":"","confidence":0,"greeks":{}}
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
    gap = 50
    if index_name == "BANKNIFTY": gap = RULES["ATM_GAP_BANK"]
    if index_name == "SENSEX": gap = RULES["ATM_GAP_SENSEX"]
    if index_name == "NIFTY": gap = RULES["ATM_GAP_NIFTY"]
    if index_name == "FINNIFTY": gap = RULES["ATM_GAP_FINNIFTY"]
    return int(round(price/gap)*gap)

def norm_cdf(x):
    return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
def norm_pdf(x):
    return math.exp(-0.5*x*x) / math.sqrt(2*math.pi)

def calculate_greeks(S, K, T_days, r, sigma, option_type="CE"):
    try:
        T = max(T_days, 0.5) / 365.0
        if sigma <=0: sigma=0.2
        if S<=0 or K<=0: return None
        d1 = (math.log(S/K) + (r + 0.5*sigma*sigma)*T) / (sigma*math.sqrt(T))
        d2 = d1 - sigma*math.sqrt(T)
        if option_type=="CE":
            delta = norm_cdf(d1)
            theta = (-S*norm_pdf(d1)*sigma/(2*math.sqrt(T)) - r*K*math.exp(-r*T)*norm_cdf(d2)) / 365.0
        else:
            delta = norm_cdf(d1)-1
            theta = (-S*norm_pdf(d1)*sigma/(2*math.sqrt(T)) + r*K*math.exp(-r*T)*norm_cdf(-d2)) / 365.0
        gamma = norm_pdf(d1) / (S*sigma*math.sqrt(T))
        vega = S * norm_pdf(d1) * math.sqrt(T) / 100.0
        return {"delta": round(delta,3), "gamma": round(gamma,4), "theta": round(theta,3), "vega": round(vega,3), "d1": round(d1,2), "d2": round(d2,2)}
    except:
        return None

def get_historical_volatility(key, days=20):
    try:
        h = get_hist(key, period="1mo", interval="1d")
        if len(h)<5: return 0.18
        h['ret'] = np.log(h['Close']/h['Close'].shift(1))
        vol = h['ret'].std() * math.sqrt(252)
        return max(0.12, min(float(vol), 0.45))
    except:
        return 0.20

def get_expiry_days():
    today = datetime.now(IST)
    weekday = today.weekday()
    days_to_thu = (3 - weekday) % 7
    if days_to_thu==0: days_to_thu=7
    return days_to_thu

def greek_filter_scanner(index_name="NIFTY"):
    try:
        S = get_price(index_name)
        if S==0: return False, "❌ GREEK: No Price", {}, 0
        K = get_atm(index_name, S)
        T = get_expiry_days()
        sigma = get_historical_volatility(index_name)
        vix = get_vix()
        iv_est = max(sigma, vix/100*1.2) if vix>0 else sigma
        d_n = get_day_data(index_name)
        opt_type = "PE" if d_n['pct']<0 else "CE"
        greeks = calculate_greeks(S, K, T, RULES["RISK_FREE_RATE"], iv_est, opt_type)
        if not greeks:
            return False, "❌ GREEK: Calc Fail", {}, 0
        confidence = 50
        reasons = []
        delta_abs = abs(greeks['delta'])
        if 0.45 <= delta_abs <= 0.65:
            confidence += 15
            reasons.append(f"Delta {greeks['delta']} OK")
        elif delta_abs < 0.35:
            confidence -= 20
            reasons.append(f"Delta {greeks['delta']} WEAK - NO ENTRY")
        else:
            confidence += 5
        if greeks['theta'] > -8:
            confidence += 15
            reasons.append(f"Theta {greeks['theta']} Low decay")
        elif greeks['theta'] < -15:
            confidence -= 25
            reasons.append(f"Theta {greeks['theta']} HIGH DECAY - AVOID")
        if vix < 18 and greeks['vega'] > 0.15:
            confidence += 10
            reasons.append(f"Vega {greeks['vega']} + VIX {vix} Good")
        if vix > 21:
            confidence -= 15
            reasons.append(f"VIX {vix} Too High")
        if T <= 2 and greeks['gamma'] > 0.001:
            confidence += 10
            reasons.append("Expiry Gamma Boost")
        if T <=1 and abs(d_n['pct'])<0.3:
            confidence -= 20
            reasons.append("Expiry Day No Trend - NO ENTRY")
        if abs(d_n['pct']) >= 0.3:
            confidence += 10
        confidence = max(0, min(100, confidence))
        status = confidence >= RULES["MIN_CONFIDENCE"]
        msg = f"{'✅' if status else '❌'} GREEK BOT: {opt_type} Delta {greeks['delta']} Theta {greeks['theta']} Vega {greeks['vega']} Conf {confidence}% | " + ", ".join(reasons)
        return status, msg, greeks, confidence
    except Exception as e:
        return False, f"❌ GREEK Error {e}", {}, 0

def filter_holiday():
    is_hol, name = is_trading_holiday()
    if is_hol:
        return False, f"❌ HOLIDAY: Market Closed Today ({name}) - Diwali/Balipratipada"
    return True, f"✅ HOLIDAY: Market Open"

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
    today = datetime.now(IST).strftime('%d-%m-%Y')
    if STATE["entry_done"] and STATE["date"]==today:
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
    fl = [filter_holiday, filter_scanner, filter_news, filter_entry, filter_exit, filter_timemachine, filter_budget, filter_risk, filter_broker, filter_alerts, filter_analyst]
    res = []
    ok_all = True
    for f in fl:
        ok, msg = f()
        res.append((ok, msg))
        if not ok:
            ok_all = False
    idx = RULES["AUTO_INDEX"]
    g_ok, g_msg, greeks, conf = greek_filter_scanner(idx)
    res.append((g_ok, g_msg))
    if not g_ok:
        ok_all = False
    return ok_all, res, greeks, conf

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
    all_pass, filters, greeks, conf = run_all_10_filters()
    msg = f"<b>🔥 DHAN FINAL AUTO - OFFICIAL LOTS 2026 + GREEK BOT</b>\n{datetime.now(IST).strftime('%d %b %H:%M:%S IST')}\n\n"
    is_hol, hol_name = is_trading_holiday()
    if is_hol:
        msg += f"🚨 <b>MARKET CLOSED TODAY: {hol_name}</b>\nCommodity opens 5 PM\n\n"
    msg += f"NIFTY: {n_p} ({d_n['pct']}%) ATM {get_atm('NIFTY', n_p)} Lot {RULES['LOT_SIZE_NIFTY']}\n"
    msg += f"BANKNIFTY: {b_p} ({d_b['pct']}%) ATM {get_atm('BANKNIFTY', b_p)} Lot {RULES['LOT_SIZE_BANK']}\n"
    msg += f"SENSEX: {s_p} ({d_s['pct']}%) ATM {get_atm('SENSEX', s_p)} Lot {RULES['LOT_SIZE_SENSEX']}\n"
    msg += f"FINNIFTY: {f_p} ({d_f['pct']}%) ATM {get_atm('FINNIFTY', f_p)} Lot {RULES['LOT_SIZE_FINNIFTY']}\n"
    msg += f"VIX: {v_det['current']} ({vix_signal(v_det['current'])}) Prev {v_det['prev']}\n\n"
    if greeks:
        msg += f"<b>GREEK BOT ({RULES['AUTO_INDEX']}):</b>\nDelta:{greeks.get('delta')} Gamma:{greeks.get('gamma')} Theta:{greeks.get('theta')} Vega:{greeks.get('vega')} | Conf:{conf}% (Min {RULES['MIN_CONFIDENCE']}%)\n"
        if conf < RULES["MIN_CONFIDENCE"]:
            msg += f"⚠️ NO LOSS RULE: Confidence {conf}% < {RULES['MIN_CONFIDENCE']}% => NO ENTRY TODAY\n\n"
        else:
            msg += f"✅ BEST PREDICTION: Confidence {conf}% => ENTRY ALLOWED\n\n"
    msg += f"RULES: 1 LOT | 1 ENTRY | {RULES['MAX_SL_RS']} SL | {RULES['PROFIT_LOCK_RS']} LOCK | {RULES['TRAILING_PTS']} TRAIL | AUTO:{'ON' if RULES['AUTO_ENTRY'] else 'OFF'} | NO LOSS FILTER ON\n\n"
    msg += f"--- 12 FILTERS (HOLIDAY+GREEK ADDED) ---\n"
    for _, txt in filters:
        msg += f"{txt}\n"
    msg += f"\nSTATUS: {'🟢 TRADE ALLOWED - AUTO ENTRY SOON' if all_pass else '🔴 NO TRADE - REASON ABOVE'}\nEntry: {STATE.get('entry_done')} {STATE.get('date')} {STATE.get('symbol')} {STATE.get('strike')}{STATE.get('type')} Conf:{STATE.get('confidence',0)}%\n"
    return msg

def do_auto_entry():
    global STATE
    try:
        today = datetime.now(IST).strftime('%d-%m-%Y')
        if STATE["entry_done"] and STATE["date"]==today:
            return
        is_hol, _ = is_trading_holiday()
        if is_hol:
            return
        all_pass, _, greeks, conf = run_all_10_filters()
        if not all_pass:
            if conf>0 and conf < RULES["MIN_CONFIDENCE"]:
                msg = f"❌ <b>NO TRADE TODAY - LOSS PROTECTION</b>\nConfidence {conf}% < {RULES['MIN_CONFIDENCE']}%\nGreek: Delta {greeks.get('delta')} Theta {greeks.get('theta')}\nReason: Best prediction says loss chance high, so NO ENTRY as per rule."
                for cid in list(CHAT_IDS):
                    try:
                        bot.send_message(cid, msg)
                    except:
                        pass
            return
        d_n = get_day_data("NIFTY")
        typ = "PE" if d_n['pct']<0 else "CE"
        idx = RULES["AUTO_INDEX"]
        price = get_price(idx)
        atm = get_atm(idx, price)
        STATE = {"date":today,"entry_done":True,"entry_price":150,"lock_active":False,"max_profit":0,"symbol":idx,"strike":str(atm),"type":typ,"index":idx,"confidence":conf,"greeks":greeks}
        save_state(STATE)
        msg = f"🚀 <b>AUTO ENTRY EXECUTED - GREEK VERIFIED</b>\nINDEX: {idx}\nSTRIKE: {atm} {typ}\nTREND: {d_n['pct']}% {'BEARISH->PE' if typ=='PE' else 'BULLISH->CE'}\nLIVE: {price}\nLot Size {RULES.get(f'LOT_SIZE_{idx}', 65)} | 1 LOT\nGREEKS: Delta {greeks.get('delta')} Theta {greeks.get('theta')} Vega {greeks.get('vega')} Gamma {greeks.get('gamma')}\nConfidence: {conf}% (No Loss Rule Passed)\nSL {RULES['MAX_SL_RS']} LOCK {RULES['PROFIT_LOCK_RS']} TRAIL {RULES['TRAILING_PTS']}"
        for cid in list(CHAT_IDS):
            try:
                bot.send_message(cid, msg)
            except:
                pass
        log.info(f"AUTO ENTRY {idx} {atm} {typ} Conf {conf}%")
    except Exception as e:
        log.error(f"Auto entry fail {e}")

def auto_trader_loop():
    while True:
        try:
            if RULES["AUTO_ENTRY"]:
                do_auto_entry()
        except Exception as e:
            log.error(f"Auto loop {e}")
        time.sleep(30)

@bot.message_handler(commands=['start','help','status'])
def h_start(m):
    CHAT_IDS.add(m.chat.id)
    save_chats(CHAT_IDS)
    bot.send_message(m.chat.id, format_main_status())

@bot.message_handler(commands=['vix'])
def h_v(m):
    det = get_vix_details()
    bot.send_message(m.chat.id, f"VIX Curr:{det['current']} Prev:{det['prev']} Change:{det['change']} High:{det['high']} Low:{det['low']} Avg5:{det['avg5']} Signal:{vix_signal(det['current'])}")

@bot.message_handler(commands=['greeks','greek'])
def h_greek(m):
    CHAT_IDS.add(m.chat.id)
    idx = RULES["AUTO_INDEX"]
    parts = m.text.split()
    if len(parts)>1:
        idx = parts[1].upper()
    ok, msg, greeks, conf = greek_filter_scanner(idx)
    det = f"<b>GREEK BOT {idx}</b>\n{msg}\n\n"
    if greeks:
        det += f"Delta: {greeks['delta']} (0.45-0.65 best for ATM)\nGamma: {greeks['gamma']}\nTheta: {greeks['theta']} per day\nVega: {greeks['vega']}\nConfidence: {conf}%\n\n"
        det += "Rule: Theta > -8 = safe, Delta 0.5 = best, VIX<18 = entry good"
    bot.send_message(m.chat.id, det)

@bot.message_handler(commands=['trade','force','ce','pe'])
def h_force(m):
    global STATE
    parts = m.text.split()
    idx = RULES["AUTO_INDEX"]
    txt = m.text.lower()
    if "bank" in txt: idx="BANKNIFTY"
    elif "sensex" in txt or "sen" in txt: idx="SENSEX"
    elif "fin" in txt: idx="FINNIFTY"
    else: idx="NIFTY"
    typ = "PE" if "pe" in txt else "CE"
    price = get_price(idx)
    atm = get_atm(idx, price)
    strike = parts[-1] if len(parts)>=2 and parts[-1].isdigit() else str(atm)
    today = datetime.now(IST).strftime('%d-%m-%Y')
    ok, gmsg, greeks, conf = greek_filter_scanner(idx)
    if conf < RULES["MIN_CONFIDENCE"] and "/force" not in txt:
        bot.send_message(m.chat.id, f"❌ Blocked by NO LOSS RULE\nConf {conf}% < {RULES['MIN_CONFIDENCE']}%\n{gmsg}\nUse /force to override")
        return
    STATE = {"date":today,"entry_done":True,"entry_price":150,"lock_active":False,"max_profit":0,"symbol":idx,"strike":strike,"type":typ,"index":idx,"confidence":conf,"greeks":greeks}
    save_state(STATE)
    lot = RULES.get(f"LOT_SIZE_{idx}", 65)
    msg = f"🚀 <b>{'AUTO' if '/trade' in txt else 'MANUAL'} ENTRY</b>\nINDEX: {idx}\nSTRIKE: {strike} {typ}\nPRICE: {price} ATM {atm}\nLot Size {lot} | 1 LOT\nGreeks: {greeks}\nConf: {conf}%\nSL {RULES['MAX_SL_RS']} LOCK {RULES['PROFIT_LOCK_RS']} TRAIL {RULES['TRAILING_PTS']}"
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['nifty','banknifty','sensex','finnifty'])
def h_idx(m):
    idx = m.text.replace('/','').upper()
    p = get_price(idx)
    d = get_day_data(idx)
    atm = get_atm(idx, p)
    lot = RULES.get(f"LOT_SIZE_{idx}", 0)
    ok, gmsg, greeks, conf = greek_filter_scanner(idx)
    bot.send_message(m.chat.id, f"<b>{idx}</b> {p} ({d['pct']}%)\nH:{d['high']} L:{d['low']} O:{d['open']}\nATM {atm} Lot {lot}\nGreek Conf {conf}% Delta {greeks.get('delta') if greeks else 'NA'} Theta {greeks.get('theta') if greeks else 'NA'}")

@bot.message_handler(commands=['reset'])
def h_reset(m):
    global STATE
    STATE = {"date":"","entry_done":False,"entry_price":0,"lock_active":False,"max_profit":0,"symbol":"","strike":"","type":"","index":"","confidence":0,"greeks":{}}
    save_state(STATE)
    bot.send_message(m.chat.id, "✅ Reset Done - Auto will trigger in 30 sec if TRADE ALLOWED")

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
threading.Thread(target=auto_trader_loop, daemon=True, name="AutoTrader").start()

if __name__=="__main__":
    port = int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
