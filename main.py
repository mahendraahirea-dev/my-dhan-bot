import os, time, threading, logging, random
from datetime import datetime
from flask import Flask
import telebot, yfinance as yf, pandas as pd

BOT_TOKEN = os.getenv("BOT_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML")
app = Flask(__name__)
log = logging.getLogger("Dhan380")

@app.route('/')
def home(): return "DHAN 380 BOT - LIVE WITH VIX"
@app.route('/health')
def health(): return {"status":"ok","time":str(datetime.now())}

SYMBOLS = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","VIX":"^INDIAVIX","FINNIFTY":"^CNXFIN","MIDCPNIFTY":"^NSEMDCP50"}
CACHE = {}; CACHE_TIME = {}; CACHE_EXPIRY = 25

def get_history(key, period="1d", interval="1m"):
    try:
        sym = SYMBOLS.get(key, key)
        return yf.Ticker(sym).history(period=period, interval=interval, auto_adjust=True)
    except: return pd.DataFrame()

def get_price(key):
    try:
        now = time.time()
        if key in CACHE and now - CACHE_TIME.get(key,0) < CACHE_EXPIRY: return CACHE[key]
        hist = get_history(key)
        if hist.empty: return CACHE.get(key,0)
        price = round(float(hist['Close'].iloc[-1]),2)
        CACHE[key]=price; CACHE_TIME[key]=now
        return price
    except: return CACHE.get(key,0)

def get_day_data(key):
    try:
        hist = get_history(key, period="1d", interval="5m")
        if hist.empty: return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}
        high = round(float(hist['High'].max()),2); low = round(float(hist['Low'].min()),2)
        open_p = round(float(hist['Open'].iloc[0]),2); close = round(float(hist['Close'].iloc[-1]),2)
        change = round(close-open_p,2); pct = round((change/open_p*100) if open_p else 0,2)
        return {"high":high,"low":low,"open":open_p,"close":close,"change":change,"pct":pct}
    except: return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}

# ===== VIX FULL CALCULATION - TUJHA MAIN POINT =====
def get_vix():
    try:
        p = get_price("VIX")
        if p==0:
            h = get_history("VIX", period="5d", interval="1d")
            if not h.empty: p = float(h['Close'].iloc[-1])
        return round(p,2)
    except: return 0

def get_vix_details():
    try:
        hist = get_history("VIX", period="5d", interval="1d")
        if hist.empty: return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0}
        curr = round(float(hist['Close'].iloc[-1]),2); high = round(float(hist['High'].iloc[-1]),2)
        low = round(float(hist['Low'].iloc[-1]),2); prev = round(float(hist['Close'].iloc[-2]),2) if len(hist)>1 else curr
        return {"current":curr,"high":high,"low":low,"prev":prev,"change":round(curr-prev,2)}
    except: return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0}

def vix_signal(vix):
    if vix==0: return "DATA NA"
    if vix < 11: return "VERY LOW - Range, Selling Best"
    if vix < 13: return "LOW - Range, Selling Fav"
    if vix < 15: return "NORMAL - Normal Move"
    if vix < 17.5: return "HIGH - Big Moves, Strict SL"
    if vix < 21: return "VERY HIGH - Scalp Only"
    return "EXTREME - Avoid"

def vix_trading_rule(vix):
    if vix < 12: return "Premium Sasta, Fast Decay - Selling Kar"
    elif vix < 15: return "Balanced - CE/PE Dono"
    elif vix < 18: return "Premium Mehenga - Buying Accha"
    else: return "Bahut Mehenga - Sirf Scalp"

def market_bias(vix, pct=0):
    if vix > 20: return "HIGH RISK - CAUTIOUS"
    if pct > 0.6: return "BULLISH"
    if pct < -0.6: return "BEARISH"
    return "SIDEWAYS"

def round_strike(price, base=50): return int(round(price/base)*base)
def get_atm(key): return round_strike(get_price(key), 100 if key=="BANKNIFTY" else 50)
def calc_levels(e, typ="CE"):
    e=float(e); sl=round(e*0.70,2); sl2=round(e-35,2); t1=round(e*1.4,2); t2=round(e*2.0,2); t3=round(e*3.0,2)
    return {"SL":sl,"SL2":sl2,"T1":t1,"T2":t2,"T3":t3}

def format_main():
    p={"NIFTY":get_price("NIFTY"),"BANKNIFTY":get_price("BANKNIFTY"),"SENSEX":get_price("SENSEX"),"VIX":get_vix(),"FINNIFTY":get_price("FINNIFTY")}
    d_n=get_day_data("NIFTY"); d_b=get_day_data("BANKNIFTY"); atm_n=get_atm("NIFTY"); atm_b=get_atm("BANKNIFTY")
    vix_det=get_vix_details(); vs=vix_signal(vix_det['current'])
    msg=f"<b>🔥 DHAN BOT 380 - FULL LIVE</b>\n{datetime.now().strftime('%d %b %H:%M:%S')}\n\n"
    msg+=f"<b>NIFTY:</b> {p['NIFTY']} ({d_n['pct']}%) H:{d_n['high']} L:{d_n['low']}\nATM:{atm_n}\n\n"
    msg+=f"<b>BANKNIFTY:</b> {p['BANKNIFTY']} ({d_b['pct']}%) ATM:{atm_b}\n<b>SENSEX:</b> {p['SENSEX']}\n<b>FINNIFTY:</b> {p['FINNIFTY']}\n\n"
    msg+=f"<b>VIX:</b> {vix_det['current']} ({vix_det['change']}) H:{vix_det['high']} L:{vix_det['low']}\nSignal:{vs}\nRule:{vix_trading_rule(vix_det['current'])}\n\n"
    msg+=f"/ce 23500 /pe 23500 /bankce 54500 /vix /nifty /banknifty"
    return msg

def format_vix_full():
    det=get_vix_details(); sig=vix_signal(det['current']); rule=vix_trading_rule(det['current'])
    hist=get_history("VIX", period="10d", interval="1d"); avg5=round(float(hist['Close'].tail(5).mean()),2) if not hist.empty and len(hist)>=5 else 0
    msg=f"<b>📊 INDIA VIX FULL ANALYSIS</b>\n\nCurrent:{det['current']} Change:{det['change']} Prev:{det['prev']}\nHigh:{det['high']} Low:{det['low']} 5Avg:{avg5}\n\nSignal:{sig}\nRule:{rule}\n\n"
    msg+=f"<11 Very Low - Sell Best\n11-13 Low - Range\n13-15 Normal\n15-17.5 High - Big Moves\n>18 Avoid\n"
    return msg

def format_sym_full(key):
    price=get_price(key); day=get_day_data(key); atm=get_atm(key); vix=get_vix()
    msg=f"<b>{key} FULL LIVE</b>\n\nPrice:{price} ({day['pct']}%) {day['change']}\nOpen:{day['open']} H:{day['high']} L:{day['low']}\n\nATM:{atm}\nVIX:{vix} {vix_signal(vix)}\n\nEntry: /ce {atm} or /pe {atm}"
    return msg

def format_entry_full(sym, strike, typ):
    lp=get_price(sym); vix_det=get_vix_details(); day=get_day_data(sym); base_opt=100+random.randint(10,50)
    levels=calc_levels(base_opt, typ); atm=get_atm(sym); diff=int(strike)-atm
    moneyness="ATM" if diff==0 else ("ITM" if (typ=="CE" and diff<0) or (typ=="PE" and diff>0) else "OTM")
    msg=f"<b>✅ ENTRY - {sym} {strike} {typ}</b>\n\nUnderlying:{sym}@{lp} ({day['pct']}%)\nStrike:{strike}{typ} {moneyness} ATM:{atm}\nOpt Price(Demo):{base_opt}\nVIX:{vix_det['current']} {vix_signal(vix_det['current'])}\n\nSL:{levels['SL']} / {levels['SL2']}\nT1:{levels['T1']} T2:{levels['T2']} T3:{levels['T3']}\n\nNote: Real option price ke liye Dhan API lagega, Yahoo sirf Index deta hai.\n"
    return msg

@bot.message_handler(commands=['start','help'])
def h_start(m): bot.send_message(m.chat.id, format_main())
@bot.message_handler(commands=['nifty'])
def h_nifty(m): bot.send_message(m.chat.id, format_sym_full("NIFTY"))
@bot.message_handler(commands=['banknifty','bank'])
def h_bank(m): bot.send_message(m.chat.id, format_sym_full("BANKNIFTY"))
@bot.message_handler(commands=['sensex'])
def h_sensex(m): bot.send_message(m.chat.id, format_sym_full("SENSEX"))
@bot.message_handler(commands=['finnifty','fin'])
def h_fin(m): bot.send_message(m.chat.id, format_sym_full("FINNIFTY"))
@bot.message_handler(commands=['vix','indiavix'])
def h_vix(m): bot.send_message(m.chat.id, format_vix_full())
@bot.message_handler(commands=['ce','pe'])
def h_ce(m):
    typ="PE" if m.text.lower().startswith("/pe") else "CE"
    parts=m.text.split(); strike=parts[1] if len(parts)>1 else get_atm("NIFTY")
    bot.send_message(m.chat.id, format_entry_full("NIFTY", strike, typ))
@bot.message_handler(commands=['bankce','bankpe'])
def h_bankce(m):
    typ="CE" if "ce" in m.text.lower() else "PE"
    parts=m.text.split(); strike=parts[1] if len(parts)>1 else get_atm("BANKNIFTY")
    bot.send_message(m.chat.id, format_entry_full("BANKNIFTY", strike, typ))
@bot.message_handler(func=lambda m: True)
def h_any(m):
    if m.text.strip().isdigit(): bot.send_message(m.chat.id, format_entry_full("NIFTY", m.text.strip(), "CE"))
    else: bot.send_message(m.chat.id, format_main())

def run_bot():
    bot.remove_webhook(); time.sleep(4)
    while True:
        try: bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90)
        except Exception as e: log.error(f"Poll {e}"); time.sleep(15)

threading.Thread(target=run_bot, daemon=True).start()
if __name__=="__main__":
    port=int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False)
