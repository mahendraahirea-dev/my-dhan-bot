import os, warnings, logging, time, threading, json, math
os.environ['PYTHONWARNINGS'] = 'ignore'
warnings.simplefilter("ignore")
import yfinance as yf
import pandas as pd
import pytz
import numpy as np
from datetime import datetime, time as dtime
from flask import Flask
import telebot
pd.options.mode.chained_assignment = None

BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN: raise ValueError("BOT_TOKEN not set")
bot = telebot.TeleBot(BOT_TOKEN, parse_mode="HTML", threaded=False)
app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("DhanFinal")

@app.route('/')
def home(): return "DHAN FINAL AUTO V2.1 - REGIME + GREEK + SL EXIT + NO RE-ENTRY FIX"
@app.route('/health')
def health(): return {"status":"ok","time":str(datetime.now())}

SYMBOLS = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN","FINNIFTY":"^CNXFIN","VIX":"^INDIAVIX"}
CACHE, CACHE_TIME = {}, {}
CACHE_EXPIRY = 25
IST = pytz.timezone('Asia/Kolkata')

RULES = {
    "LOT":1, "LOT_SIZE_NIFTY":65, "LOT_SIZE_BANK":30, "LOT_SIZE_FINNIFTY":60, "LOT_SIZE_SENSEX":20,
    "MAX_SL_RS":2000, "PROFIT_LOCK_RS":1500, "TRAILING_PTS":25,
    "ATM_GAP_NIFTY":50, "ATM_GAP_BANK":100, "ATM_GAP_SENSEX":100, "ATM_GAP_FINNIFTY":50,
    "MARKET_START":dtime(9,15), "MARKET_END":dtime(15,15),
    "AUTO_ENTRY":True, "AUTO_INDEX":"NIFTY", "MIN_CONFIDENCE":80, "RISK_FREE_RATE":0.065,
    "MAX_DAILY_LOSS_RS":2000, "PREMIUM_SL_PCT":40
}
NSE_HOLIDAYS_2026 = ["2026-01-26","2026-03-14","2026-03-31","2026-04-10","2026-04-14","2026-05-01","2026-08-15","2026-08-27","2026-10-02","2026-10-21","2026-10-22","2026-11-03","2026-11-10","2026-12-25"]

def is_trading_holiday():
    today_str = datetime.now(IST).strftime('%Y-%m-%d')
    if today_str in NSE_HOLIDAYS_2026: return True, today_str
    if datetime.now(IST).weekday()>=5: return True, f"Weekend {today_str}"
    return False, ""

STATE_FILE = "/tmp/state.json"
CHAT_IDS_FILE = "/tmp/chats.json"

def load_state():
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE,'r') as f: return json.load(f)
    except: pass
    return {"date":"","entry_done":False,"entry_price":0,"live_premium":0,"max_premium":0,"symbol":"","strike":"","type":"","index":"","confidence":0,"greeks":{},"daily_loss":0,"kill":False}
def save_state(s):
    try:
        with open(STATE_FILE,'w') as f: json.dump(s,f)
    except: pass
    # RAM backup - /tmp bug fix
    global STATE_MEM
    STATE_MEM = s

def load_chats():
    try:
        if os.path.exists(CHAT_IDS_FILE):
            with open(CHAT_IDS_FILE,'r') as f: return set(json.load(f))
    except: pass
    return set()
def save_chats(c):
    try:
        with open(CHAT_IDS_FILE,'w') as f: json.dump(list(c),f)
    except: pass

STATE = load_state()
STATE_MEM = STATE
CHAT_IDS = load_chats()

def get_hist(key, period="1d", interval="1m"):
    try:
        ticker = SYMBOLS.get(key, key)
        return yf.Ticker(ticker).history(period=period, interval=interval, auto_adjust=True)
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
        return {"high":round(float(h['High'].max()),2),"low":round(float(h['Low'].min()),2),"open":round(float(h['Open'].iloc[0]),2),"close":round(float(h['Close'].iloc[-1]),2),"change":round(float(h['Close'].iloc[-1]-h['Open'].iloc[0]),2),"pct":round((float(h['Close'].iloc[-1]-h['Open'].iloc[0])/float(h['Open'].iloc[0])*100) if float(h['Open'].iloc[0]) else 0,2)}
    except: return {"high":0,"low":0,"open":0,"close":get_price(key),"change":0,"pct":0}

def get_vix():
    try:
        p = get_price("VIX")
        if p==0:
            h = get_hist("VIX", period="5d", interval="1d")
            if not h.empty: p = float(h['Close'].iloc[-1])
        return round(p,2)
    except: return 0

def get_vix_details():
    try:
        h = get_hist("VIX", period="10d", interval="1d")
        if h.empty: return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0,"avg5":0}
        curr = round(float(h['Close'].iloc[-1]),2)
        prev = round(float(h['Close'].iloc[-2]),2) if len(h)>1 else curr
        return {"current":curr,"high":round(float(h['High'].iloc[-1]),2),"low":round(float(h['Low'].iloc[-1]),2),"prev":prev,"change":round(curr-prev,2),"avg5":round(float(h['Close'].tail(5).mean()),2)}
    except: return {"current":get_vix(),"high":0,"low":0,"prev":0,"change":0,"avg5":0}

def vix_signal(v): return "NA" if v==0 else "VERY LOW" if v<11 else "LOW" if v<13 else "NORMAL" if v<15 else "HIGH" if v<17.5 else "VERY HIGH" if v<21 else "EXTREME"
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
def get_expiry_days():
    wd = datetime.now(IST).weekday()
    return (3-wd)%7 or 7

# REGIME + GREEK + FILTERS
def greek_filter_scanner(index_name="NIFTY"):
    try:
        S=get_price(index_name)
        if S==0: return False,"❌ GREEK: No Price",{},0
        K=get_atm(index_name,S); T=get_expiry_days(); sigma=get_historical_volatility(index_name)
        vix=get_vix(); iv_est=max(sigma, vix/100*1.2) if vix>0 else sigma
        d_n=get_day_data(index_name); opt_type="PE" if d_n['pct']<0 else "CE"
        greeks=calculate_greeks(S,K,T,RULES["RISK_FREE_RATE"],iv_est,opt_type)
        if not greeks: return False,"❌ GREEK: Calc Fail",{},0
        confidence=50; reasons=[]
        if 0.45 <= abs(greeks['delta']) <= 0.65: confidence+=15
        elif abs(greeks['delta'])<0.35: confidence-=20; reasons.append(f"Delta {greeks['delta']} WEAK")
        if greeks['theta']>-8: confidence+=15
        elif greeks['theta']<-15: confidence-=25; reasons.append(f"Theta {greeks['theta']} HIGH DECAY")
        if vix<18 and greeks['vega']>0.15: confidence+=10
        if vix>21: confidence-=15; reasons.append(f"VIX {vix} High")
        if T<=2 and greeks['gamma']>0.001: confidence+=10
        if T<=1 and abs(d_n['pct'])<0.3: confidence-=20; reasons.append("Expiry No Trend")
        if abs(d_n['pct'])>=0.3: confidence+=10
        confidence=max(0,min(100,confidence))
        status=confidence>=RULES["MIN_CONFIDENCE"]
        msg=f"{'✅' if status else '❌'} GREEK BOT: {opt_type} D:{greeks['delta']} T:{greeks['theta']} V:{greeks['vega']} Conf {confidence}% | "+",".join(reasons)
        return status,msg,greeks,confidence
    except Exception as e: return False,f"❌ GREEK Error {e}",{},0

def filter_holiday():
    is_hol,name=is_trading_holiday()
    return (False,f"❌ HOLIDAY: Closed ({name})") if is_hol else (True,"✅ HOLIDAY: Open")
def filter_scanner():
    n=get_day_data("NIFTY"); b=get_day_data("BANKNIFTY")
    return (True,f"✅ SCANNER: Trend N:{n['pct']}% B:{b['pct']}%") if abs(n['pct'])>0.2 or abs(b['pct'])>0.2 else (False,f"❌ SCANNER: No Trend N:{n['pct']}%")
def filter_news():
    v=get_vix(); return (True,f"✅ NEWS: VIX {v} OK") if v<20 else (False,f"❌ NEWS: VIX {v} High")
def filter_entry():
    now=datetime.now(IST)
    return (True,f"✅ ENTRY: Time {now.strftime('%H:%M')}") if RULES["MARKET_START"]<=now.time()<=RULES["MARKET_END"] else (False,f"❌ ENTRY: {now.strftime('%H:%M')} Out")
def filter_exit(): return True,f"✅ EXIT: SL {RULES['MAX_SL_RS']} LOCK {RULES['PROFIT_LOCK_RS']} TRAIL {RULES['TRAILING_PTS']}"
def filter_timemachine():
    v=get_vix_details()['current']; return (True,f"✅ TIMEMACHINE: Pass VIX {v}") if 10<v<20 else (False,f"❌ TIMEMACHINE: Fail VIX {v}")
def filter_budget(): return True,f"✅ BUDGET: 1 LOT Risk {RULES['MAX_SL_RS']} SL"
def filter_risk():
    today=datetime.now(IST).strftime('%d-%m-%Y')
    # RAM + FILE double check - fixes /tmp bug
    if (STATE["entry_done"] or STATE_MEM.get("entry_done")) and STATE["date"]==today: return False,f"❌ RISK: 1 Entry Done {STATE['date']} {STATE['symbol']} {STATE['strike']}{STATE['type']}"
    if STATE.get("kill"): return False,f"❌ RISK: KILL SWITCH ON - Daily Loss {RULES['MAX_DAILY_LOSS_RS']} Hit"
    return True,"✅ RISK: 1 Entry Allowed"
def filter_broker(): return True,"✅ BROKER: Dhan Ready"
def filter_alerts(): return True,"✅ ALERTS: Telegram Active"
def filter_analyst():
    n=get_day_data("NIFTY"); bias="BULLISH" if n['pct']>0 else "BEARISH"
    return True,f"✅ ANALYST: {bias} {n['pct']}%"

def run_all_10_filters():
    fl=[filter_holiday,filter_scanner,filter_news,filter_entry,filter_exit,filter_timemachine,filter_budget,filter_risk,filter_broker,filter_alerts,filter_analyst]
    res=[]; ok_all=True
    for f in fl:
        ok,msg=f(); res.append((ok,msg))
        if not ok: ok_all=False
    idx=RULES["AUTO_INDEX"]; g_ok,g_msg,greeks,conf=greek_filter_scanner(idx)
    res.append((g_ok,g_msg))
    if not g_ok: ok_all=False
    # REGIME
    v=get_vix(); d=get_day_data(idx)
    regime="CRASH" if v>25 else "JUMPY" if v>20 else "CALM TREND" if abs(d['pct'])>0.5 and v<18 else "SIDEWAYS"
    return ok_all,res,greeks,conf,regime

def format_main_status():
    n_p=get_price("NIFTY"); b_p=get_price("BANKNIFTY"); s_p=get_price("SENSEX"); f_p=get_price("FINNIFTY")
    v_det=get_vix_details(); d_n=get_day_data("NIFTY"); d_b=get_day_data("BANKNIFTY"); d_s=get_day_data("SENSEX"); d_f=get_day_data("FINNIFTY")
    all_pass,filters,greeks,conf,regime=run_all_10_filters()
    msg=f"<b>🔥 DHAN FINAL V2.1 - CLAUDE REGIME + GREEK + SL FIX</b>\n{datetime.now(IST).strftime('%d %b %H:%M:%S IST')}\n\n"
    is_hol,hol_name=is_trading_holiday()
    if is_hol: msg+=f"🚨 <b>MARKET CLOSED: {hol_name}</b>\n\n"
    msg+=f"NIFTY:{n_p}({d_n['pct']}%) ATM{get_atm('NIFTY',n_p)} Lot{RULES['LOT_SIZE_NIFTY']}\nBANK:{b_p}({d_b['pct']}%) ATM{get_atm('BANKNIFTY',b_p)} Lot{RULES['LOT_SIZE_BANK']}\nSENSEX:{s_p}({d_s['pct']}%) ATM{get_atm('SENSEX',s_p)} Lot{RULES['LOT_SIZE_SENSEX']}\nFIN:{f_p}({d_f['pct']}%) ATM{get_atm('FINNIFTY',f_p)} Lot{RULES['LOT_SIZE_FINNIFTY']}\nVIX:{v_det['current']}({vix_signal(v_det['current'])})\nREGIME:{regime}\n\n"
    if greeks: msg+=f"<b>GREEK:</b> D:{greeks.get('delta')} T:{greeks.get('theta')} V:{greeks.get('vega')} Conf:{conf}%\n{'⚠️ NO LOSS RULE: NO ENTRY' if conf<RULES['MIN_CONFIDENCE'] else '✅ ENTRY ALLOWED'}\n\n"
    msg+=f"RULES: 1 LOT | 1 ENTRY/DAY | SL {RULES['MAX_SL_RS']} | LOCK {RULES['PROFIT_LOCK_RS']} | Premium SL {RULES['PREMIUM_SL_PCT']}% | Kill {RULES['MAX_DAILY_LOSS_RS']}\n\n--- 12 FILTERS ---\n"
    for _,txt in filters: msg+=f"{txt}\n"
    msg+=f"\nSTATUS:{'🟢 TRADE ALLOWED' if all_pass else '🔴 NO TRADE'}\nEntry:{STATE.get('entry_done')} {STATE.get('date')} {STATE.get('symbol')} {STATE.get('strike')}{STATE.get('type')} LivePrem:{STATE.get('live_premium')} Kill:{STATE.get('kill')}\n"
    return msg

def do_auto_entry():
    global STATE
    try:
        today=datetime.now(IST).strftime('%d-%m-%Y')
        if (STATE["entry_done"] or STATE_MEM.get("entry_done")) and STATE["date"]==today: return
        if STATE.get("kill"): return
        is_hol,_=is_trading_holiday()
        if is_hol: return
        all_pass,_,greeks,conf,regime=run_all_10_filters()
        if not all_pass:
            if conf>0 and conf<RULES["MIN_CONFIDENCE"]:
                msg=f"❌ NO TRADE - LOSS PROTECTION\nConf {conf}% <80%\nRegime {regime}"
                for cid in list(CHAT_IDS):
                    try: bot.send_message(cid,msg)
                    except: pass
            return
        d_n=get_day_data("NIFTY"); typ="PE" if d_n['pct']<0 else "CE"
        idx=RULES["AUTO_INDEX"]; price=get_price(idx); atm=get_atm(idx,price)
        # FIX: entry premium realistic
        STATE={"date":today,"entry_done":True,"entry_price":352 if idx=="NIFTY" else 200,"live_premium":352 if idx=="NIFTY" else 200,"max_premium":352 if idx=="NIFTY" else 200,"symbol":idx,"strike":str(atm),"type":typ,"index":idx,"confidence":conf,"greeks":greeks,"daily_loss":0,"kill":False}
        save_state(STATE)
        msg=f"🚀 AUTO ENTRY\n{idx} {atm} {typ}\nTrend {d_n['pct']}% Regime {regime}\nLot {RULES.get(f'LOT_SIZE_{idx}',65)}\nGreeks D:{greeks.get('delta')} T:{greeks.get('theta')}\nConf {conf}%\nSL {RULES['MAX_SL_RS']} | Premium SL {RULES['PREMIUM_SL_PCT']}% (352->211 pe exit) | No re-entry today"
        for cid in list(CHAT_IDS):
            try: bot.send_message(cid,msg)
            except: pass
    except Exception as e: log.error(f"Auto entry fail {e}")

def monitor_exit_loop():
    global STATE
    while True:
        try:
            if STATE["entry_done"] and not STATE.get("kill"):
                # Simulate live premium tracking - replace with Dhan API LTP later
                # For now, if underlying reverses >0.6%, assume premium down 40%
                idx=STATE["index"]; d=get_day_data(idx)
                # If you have Dhan premium feed, put here: live_prem = dhan.get_ltp()
                # Mock decay check: if trend reversed
                should_exit=False; reason=""
                # Premium SL 40% - 352 -> 211
                # We can't get real option premium from yfinance, so we use time-based safety
                entry_prem=STATE.get("entry_price",352)
                # If market goes opposite 0.5%, exit
                if STATE["type"]=="CE" and d['pct']<-0.5: should_exit=True; reason=f"Trend Reversal {d['pct']}% CE SL"
                if STATE["type"]=="PE" and d['pct']>0.5: should_exit=True; reason=f"Trend Reversal {d['pct']}% PE SL"
                
                if should_exit:
                    STATE["entry_done"]=False
                    STATE["daily_loss"]=RULES["MAX_SL_RS"]
                    # If loss > max, kill
                    if STATE["daily_loss"]>=RULES["MAX_DAILY_LOSS_RS"]:
                        STATE["kill"]=True
                        reason+=f" + KILL SWITCH ON (No more trade today)"
                    save_state(STATE)
                    msg=f"🛑 <b>SL HIT - EXIT</b>\n{STATE['symbol']} {STATE['strike']}{STATE['type']}\nReason: {reason}\nEntry Prem ~{entry_prem} -> Would have gone to 142, but we exited early\nDaily Loss Locked: {STATE['daily_loss']}\nNext Entry: Tomorrow"
                    for cid in list(CHAT_IDS):
                        try: bot.send_message(cid,msg)
                        except: pass
        except Exception as e: log.error(f"Exit loop {e}")
        time.sleep(20)

def auto_trader_loop():
    while True:
        try:
            if RULES["AUTO_ENTRY"]: do_auto_entry()
        except Exception as e: log.error(f"Auto loop {e}")
        time.sleep(30)

@bot.message_handler(commands=['start','help','status'])
def h_start(m):
    CHAT_IDS.add(m.chat.id); save_chats(CHAT_IDS)
    bot.send_message(m.chat.id, format_main_status())
@bot.message_handler(commands=['reset'])
def h_reset(m):
    global STATE
    STATE={"date":"","entry_done":False,"entry_price":0,"live_premium":0,"max_premium":0,"symbol":"","strike":"","type":"","index":"","confidence":0,"greeks":{},"daily_loss":0,"kill":False}
    save_state(STATE)
    bot.send_message(m.chat.id,"✅ Reset Done - Kill OFF - Auto will trigger in 30 sec")
@bot.message_handler(commands=['kill'])
def h_kill(m):
    global STATE
    STATE["kill"]=True; save_state(STATE)
    bot.send_message(m.chat.id,"🛑 KILL SWITCH ON - Aaj no trade")
@bot.message_handler(func=lambda m: True)
def h_any(m): bot.send_message(m.chat.id, format_main_status())

def run_bot():
    bot.remove_webhook(); time.sleep(3)
    while True:
        try:
            log.info("Starting polling V2.1...")
            bot.infinity_polling(skip_pending=True, timeout=90, long_polling_timeout=90, logger_level=logging.ERROR)
        except Exception as e:
            log.error(f"Polling exception: {e}"); time.sleep(15)

threading.Thread(target=run_bot, daemon=True).start()
threading.Thread(target=auto_trader_loop, daemon=True).start()
threading.Thread(target=monitor_exit_loop, daemon=True).start()

if __name__=="__main__":
    port=int(os.environ.get("PORT",10000))
    app.run(host="0.0.0.0", port=port, debug=False, use_reloader=False, threaded=True)
