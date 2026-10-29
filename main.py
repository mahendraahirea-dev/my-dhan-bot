# main.py - V33.1 FINAL AUTO PAPER - NO CRASH - NO PYTZ - 100% AUTO
import os, time, threading, requests, traceback
from fastapi import FastAPI
from datetime import datetime, time as dtime, timezone, timedelta

app = FastAPI()

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
DHAN_ID = os.environ.get("DHAN_CLIENT_ID","").strip()
DHAN_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN","").strip()

IST = timezone(timedelta(hours=5, minutes=30))
AUTO_TRADING = True
CHAT_IDS = set()
TODAY_TRADES = []
CURRENT_POSITIONS = {}
SYMBOLS = ["NIFTY","BANKNIFTY","SENSEX","RELIANCE","HDFCBANK"]

print("🔥 V33.1 FINAL LOADING...")

def get_dhan():
    try:
        from dhanhq import dhanhq
        if not DHAN_ID or not DHAN_TOKEN: return None
        return dhanhq(DHAN_ID, DHAN_TOKEN)
    except Exception as e:
        print(f"Dhan init err {e}")
        return None

def send_all(text):
    for cid in list(CHAT_IDS):
        try:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=10)
        except: pass

def send_one(cid, text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=15)
    except Exception as e:
        print(f"send err {e}")

def get_spot_price(underlying):
    try:
        dhan = get_dhan()
        if not dhan: return 0
        mapping = {"NIFTY":13,"BANKNIFTY":25,"SENSEX":51,"RELIANCE":2885,"HDFCBANK":1333}
        sid = mapping.get(underlying,13)
        try:
            r = dhan.get_ltp_data(securities={"IDX_I": [sid]})
            price = float(r['data']['IDX_I'][str(sid)]['last_price'])
            if price>0: return price
        except: pass
        try:
            r = dhan.get_ltp_data(securities={"NSE_EQ": [sid]})
            return float(r['data']['NSE_EQ'][str(sid)]['last_price'])
        except: pass
        return 0
    except Exception as e:
        print(f"spot err {underlying} {e}")
        return 0

def get_option_ltp(underlying, strike, opt_type):
    try:
        dhan = get_dhan()
        if not dhan: return 0, None, None
        exp_list = dhan.get_expiry_list(underlying_symbol=underlying, exchange_segment="NSE_FNO")
        if not exp_list or 'data' not in exp_list or not exp_list['data']: return 0, None, None
        expiry = exp_list['data'][0]
        chain = dhan.get_option_chain(underlying_symbol=underlying, exchange_segment="NSE_FNO", expiry=expiry)
        if not chain or 'data' not in chain: return 0, None, None
        oc = chain['data'].get('oc',{})
        if isinstance(oc, dict): oc = list(oc.values())
        for o in oc:
            try:
                if int(float(o.get('strike_price',0))) == int(strike) and str(o.get('option_type','')).upper() == opt_type:
                    ltp = float(o.get('last_price',0) or 0)
                    sym = o.get('trading_symbol') or f"{underlying} {strike} {opt_type}"
                    return ltp, sym, expiry
            except: continue
        return 0, None, None
    except:
        return 0, None, None

def get_atm(spot, underlying):
    try:
        if underlying in ["NIFTY","SENSEX"]: return int(round(spot/50)*50)
        elif underlying=="BANKNIFTY": return int(round(spot/100)*100)
        else: return int(round(spot/5)*5)
    except: return int(spot)

def paper_multi_loop():
    print("📝 V33.1 MULTI PAPER STARTED - NIFTY BANK SENSEX REL HDFC - NO PYTZ - NO CRASH")
    while True:
        try:
            now = datetime.now(IST)
            cur_time = now.time()
            if cur_time < dtime(9,15) or cur_time > dtime(15,20):
                time.sleep(60)
                continue
            if not AUTO_TRADING:
                time.sleep(15)
                continue
            for underlying in SYMBOLS:
                try:
                    spot = get_spot_price(underlying)
                    if spot==0:
                        time.sleep(1)
                        continue
                    atm = get_atm(spot, underlying)
                    if underlying not in CURRENT_POSITIONS:
                        for opt_type in ["PE","CE"]:
                            try:
                                ltp, sym, exp = get_option_ltp(underlying, atm, opt_type)
                                if 10 < ltp < 350 and sym:
                                    qty = 75 if underlying=="NIFTY" else 30 if underlying=="BANKNIFTY" else 20 if underlying=="SENSEX" else 250 if underlying=="RELIANCE" else 300
                                    sl = max(5, ltp - (2000/qty))
                                    pos = {"underlying":underlying,"symbol":sym,"buy_price":ltp,"buy_time":now.strftime('%Y-%m-%d %H:%M:%S'),"buy_spot":spot,"qty":qty,"highest":ltp,"sl_price":sl,"strike":atm,"type
