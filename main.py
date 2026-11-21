import os, warnings, logging, time, math
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.simplefilter("ignore")
import yfinance as yf
import pandas as pd
import pytz
import numpy as np
from datetime import datetime, time as dtime
from flask import Flask
import telebot

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN not set")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("Scanner")

@app.route('/')
def home(): return "DHAN PAPER SCANNER V3 - BEST 4 MANUAL"
@app.route('/health')
def health(): return {"status":"ok","time":str(datetime.now())}

SYMBOLS = {
    "NIFTY":"^NSEI",
    "BANKNIFTY":"^NSEBANK",
    "SENSEX":"^BSESN",
    "FINNIFTY":"^CNXFIN",
    "VIX":"^INDIAVIX"
}
IST = pytz.timezone('Asia/Kolkata')

RULES = {
    "LOT_SIZE_NIFTY":65, "LOT_SIZE_BANK":30, 
    "LOT_SIZE_FINNIFTY":60, "LOT_SIZE_SENSEX":20,
    "ATM_GAP_NIFTY":50, "ATM_GAP_BANK":100, 
    "ATM_GAP_SENSEX":100, "ATM_GAP_FINNIFTY":50,
    "MIN_CONFIDENCE":80, "RISK_FREE_RATE":0.065,
    "INDICES": ["NIFTY","BANKNIFTY","SENSEX","FINNIFTY"]
}

# Simple cache to avoid 【entity-Yahoo¦canonical_name=Yahoo】 rate limit
CACHE, CACHE_TIME = {}, {}
CACHE_EXPIRY = 25

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
        if h.empty: return CACHE.get(key,0)
        p = round(float(h['Close'].iloc[-1]),2)
        CACHE[key]=p; CACHE_TIME[key]=now
        return p
    except: 
        return CACHE.get(key,0)

def get_day_data(key):
    try:
        h = get_hist(key, period="1d", interval="5m")
        if h.empty: 
            return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}
        return {
            "high":round(float(h['High'].max()),2),
            "low":round(float(h['Low'].min()),2),
            "open":round(float(h['Open'].iloc[0]),2),
            "close":round(float(h['Close'].iloc[-1]),2),
            "change":round(float(h['Close'].iloc[-1]-h['Open'].iloc[0]),2),
            "pct":round((float(h['Close'].iloc[-1]-h['Open'].iloc[0])/float(h['Open'].iloc[0])*100) if float(h['Open'].iloc[0]) else 0,2)
        }
    except: 
        return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}

def get_vix():
    try:
        p = get_price("VIX")
        if p==0:
            h = get_hist("VIX", period="5d", interval="1d")
            if not h.empty: p = float(h['Close'].iloc[-1])
        return round(p,2)
    except: return 0

def get_atm(idx, price):
    gap = RULES["ATM_GAP_NIFTY"] if idx=="NIFTY" else RULES["ATM_GAP_BANK"] if idx=="BANKNIFTY" else RULES["ATM_GAP_SENSEX"] if idx=="SENSEX" else RULES["ATM_GAP_FINNIFTY"]
    return int(round(price/gap)*gap)

def norm_cdf(x): return (1.0 + math.erf(x / math.sqrt(2.0))) / 2.0
def norm_pdf(x): return math.exp(-0.5*x*x) / math.sqrt(2*math.pi)

def calculate_greeks(S,K,T_days,r,sigma,opt_type="CE"):
    try:
        T = max(T_days,0.5)/365.0
        if sigma<=0: sigma=0.2
        d1 = (math.log(S/K)+(r+0.5*sigma*sigma)*T)/(sigma*math.sqrt(T))
        d2 = d1 - sigma*math.sqrt(T)
        if opt_type=="CE":
            delta = norm_cdf(d1)
            theta = (-S*norm_pdf(d1)*sigma/(2*math.sqrt(T)) - r*K*math.exp(-r*T)*norm_cdf(d2))/365.0
        else:
            delta = norm_cdf(d1)-1
            theta = (-S*norm_pdf(d1)*sigma/(2*math.sqrt(T)) + r*K*math.exp(-r*T)*norm_cdf(-d2))/365.0
        gamma = norm_pdf(d1)/(S*sigma*math.sqrt(T))
        vega = S * norm_pdf(d1) * math.sqrt(T) / 100.0
        return {"delta":round(delta,3),"gamma":round(gamma,4),"theta":round(theta,3),"vega":round(vega,3)}
    except: return None

def get_historical_volatility(key, days=20):
    try:
        h = get_hist(key, period="1mo", interval="1d")
        if len(h)<5: return 0.18
        h['ret']=np.log(h['Close']/h['Close'].shift(1))
        return max(0.12, min(float(h['ret'].std()*math.sqrt(252)),0.45))
    except: return 0.20

def get_expiry_days(index):
    # Corrected: NIFTY Tue, BANKNIFTY Thu, SENSEX Fri, FINNIFTY Tue
    wd = datetime.now(IST).weekday()
    mapping = {"NIFTY":1, "FINNIFTY":1, "BANKNIFTY":3, "SENSEX":4}
    target = mapping.get(index, 1)
    return (target - wd) % 7 or 7

def vix_signal(v): 
    return "NA" if v==0 else "VERY LOW" if v<11 else "LOW" if v<13 else "NORMAL" if v<15 else "HIGH" if v<17.5 else "VERY HIGH" if v<21 else "EXTREME"

def scan_one(index_name):
    try:
        S=get_price(index_name)
        if S==0: return False, f"❌ {index_name}: No Price", {}, 0, {}
        K=get_atm(index_name,S)
        T=get_expiry_days(index_name)
        sigma=get_historical_volatility(index_name)
        vix=get_vix()
        iv_est=max(sigma, vix/100*1.2) if vix>0 else sigma
        d_n=get_day_data(index_name)
        opt_type="PE" if d_n['pct']<0 else "CE"
        greeks=calculate_greeks(S,K,T,RULES["RISK_FREE_RATE"],iv_est,opt_type)
        if not greeks: return False,f"❌ {index_name}: Calc Fail",{},0,{}

        confidence=50; reasons=[]
        if 0.45 <= abs(greeks['delta']) <= 0.65: confidence+=15
        elif abs(greeks['delta'])<0.35: confidence-=20; reasons.append(f"Delta {greeks['delta']} WEAK")
        if greeks['theta']>-8: confidence+=15
        elif greeks['theta']<-15: confidence-=25; reasons.append(f"Theta {greeks['theta']} HIGH DECAY")
        if vix>21: confidence-=15; reasons.append(f"VIX {vix} High")
        if T<=1 and abs(d_n['pct'])<0.3: confidence-=20; reasons.append("Expiry No Trend")
        if abs(d_n['pct'])>=0.3: confidence+=10
        
        confidence=max(0,min(100,confidence))
        msg=f"{'✅' if confidence>=RULES['MIN_CONFIDENCE'] else '❌'} {index_name} {opt_type} ATM{K} Price{S} D:{greeks['delta']} T:{greeks['theta']} Conf:{confidence}% Chg:{d_n['pct']}%"
        extra = {"price":S, "pct":d_n['pct'], "atm":K, "opt_type":opt_type, "expiry_in":T}
        return confidence>=RULES['MIN_CONFIDENCE'], msg, greeks, confidence, extra
    except Exception as e:
        return False,f"❌ {index_name} Error {e}",{},0,{}

def scan_best_of_4():
    best = None; best_conf = -1; best_greeks = {}; best_extra = {}; logs = []
    for idx in RULES["INDICES"]:
        ok, msg, greeks, conf, extra = scan_one(idx)
        logs.append(msg)
        if conf > best_conf:
            best_conf = conf; best = idx; best_greeks = greeks; best_extra = extra
    return best, best_conf, best_greeks, best_extra, logs

def format_status():
    n_p=get_price("NIFTY"); b_p=get_price("BANKNIFTY"); s_p=get_price("SENSEX"); f_p=get_price("FINNIFTY")
    vix=get_vix()
    d_n=get_day_data("NIFTY"); d_b=get_day_data("BANKNIFTY"); d_s=get_day_data("SENSEX"); d_f=get_day_data("FINNIFTY")
    
    best_idx, best_conf, greeks, extra, logs = scan_best_of_4()
    
    msg = f"<b>📊 PAPER SCANNER V3 - MANUAL ENTRY HELPER</b>\n"
    msg += f"{datetime.now(IST).strftime('%d %b %H:%M:%S IST')}\n\n"
    msg += f"NIFTY:{n_p}({d_n['pct']}%) ATM{get_atm('NIFTY',n_p)}\n"
    msg += f"BANK:{b_p}({d_b['pct']}%) ATM{get_atm('BANKNIFTY',b_p)}\n"
    msg += f"SENSEX:{s_p}({d_s['pct']}%) ATM{get_atm('SENSEX',s_p)}\n"
    msg += f"FIN:{f_p}({d_f['pct']}%) ATM{get_atm('FINNIFTY',f_p)}\n"
    msg += f"VIX:{vix} ({vix_signal(vix)})\n\n"

    if best_idx:
        msg += f"<b>BEST ➜ {best_idx} {extra.get('opt_type')} {extra.get('atm')} Conf {best_conf}%</b>\n"
        if greeks:
            msg += f"Greeks D:{greeks.get('delta')} G:{greeks.get('gamma')} T:{greeks.get('theta')} V:{greeks.get('vega')}\n"
            msg += f"Expiry in {extra.get('expiry_in')} days | Index {extra.get('pct')}%\n"
        msg += f"\n{'🟢 <b>MANUAL ENTRY CAN BE CONSIDERED</b>' if best_conf>=RULES['MIN_CONFIDENCE'] else '🔴 NO TRADE - WAIT'}\n\n"
    
    msg += f"--- ALL 4 SCAN ---\n"
    for l in logs: msg+=f"{l}\n"
    
    msg += f"\nLot: NIFTY {RULES['LOT_SIZE_NIFTY']} | BANK {RULES['LOT_SIZE_BANK']} | SENSEX {RULES['LOT_SIZE_SENSEX']} | FIN {RULES['LOT_SIZE_FINNIFTY']}\n"
    msg += f"Use this only to pick ATM. Check premium on Dhan before entry."
    return msg

@bot.message_handler(commands=['start','help','status'])
def h_start(m):
    bot.send_message(m.chat.id, format_status())

@bot.message_handler(func=lambda m: True)
def h_any(m):
    bot.send_message(m.chat.id, format_status())

def run_bot():
    bot.remove_webhook(); time.sleep(2)
    while True:
        try:
            log.info("Scanner polling...")
            bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90)
        except Exception as e:
            log.error(f"Polling {e}"); time.sleep(10)

import threading
threading.Thread(target=run_bot, daemon=True).start()

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
