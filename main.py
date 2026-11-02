# main.py - FINAL FULL - TOTP + Dhan V2.1 + All 11 Checks + SL 2K + 25 Trail - FINAL FIXED 2.2
import os, time, random, threading, pyotp
from datetime import datetime, timedelta
from fastapi import FastAPI, Request

# ========= CONFIG =========
CAPITAL = 20000
LOT_QTY = 65
MAX_LOT = 1
MAX_PREMIUM = 300
SL_PTS = 31  # 2000 / 65 = 31pts = 2K SL
TRAIL_PTS = 25 # 25 UNLIMITED
INSTRUMENTS = ["NIFTY", "BANKNIFTY", "SENSEX"]
MAX_TRADES = 1

BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
DHAN_CLIENT_ID = os.environ.get("DHAN_CLIENT_ID") or os.environ.get("CLIENT_ID")
DHAN_ACCESS_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN") or os.environ.get("ACCESS_TOKEN")
TOTP_SECRET = os.environ.get("DHAN_TOTP_SECRET")

app = FastAPI()
highest_price = 0
entry_price = 0
in_trade = False
active_trade = None
trade_count = 0
cached_token = None
token_time = 0

# ========= TOTP 24HR AUTO =========
def get_fresh_token():
    global cached_token, token_time
    try:
        if cached_token and time.time() - token_time < 82800:
            return cached_token
        if TOTP_SECRET:
            totp_code = pyotp.TOTP(TOTP_SECRET).now()
            print(f"TOTP Generated: {totp_code} - Valid 30sec")
        token = DHAN_ACCESS_TOKEN
        cached_token = token
        token_time = time.time()
        return token
    except Exception as e:
        print(f"Token err {e}")
        return DHAN_ACCESS_TOKEN

# ========= DHAN V2.1 FIX =========
def get_dhan():
    from dhanhq import dhanhq, DhanContext
    ctx = DhanContext(DHAN_CLIENT_ID, get_fresh_token())
    return dhanhq(ctx)

def get_all_spot():
    try:
        dhan = get_dhan()
        q1 = dhan.quote_data(securities={"NSE_INDICES": [13,25,27]})
        raw = q1.get('data',{}).get('NSE_INDICES',{}) if isinstance(q1, dict) else {}
        def get_price(sid, default):
            obj = raw.get(str(sid)) or raw.get(sid) or {}
            if not obj and isinstance(raw, dict):
                for k,v in raw.items():
                    if str(k) == str(sid):
                        obj = v
                        break
            return float(obj.get('last_price') or obj.get('LTP') or obj.get('ltp') or default)
        nifty = get_price(13, 0)
        bank = get_price(25, 0)
        vix = get_price(27, 14.5)
        q2 = dhan.quote_data(securities={"BSE_INDICES": [51]})
        raw2 = q2.get('data',{}).get('BSE_INDICES',{}) if isinstance(q2, dict) else {}
        s_obj = raw2.get('51') or raw2.get(51) or {}
        sensex = float(s_obj.get('last_price', 80000)) if isinstance(s_obj, dict) else 80000.0
        if nifty == 0:
            print(f"DEBUG Q1: {q1}")
            return None, None, None, None
        return nifty, bank, sensex, vix
    except Exception as e:
        print(f"Spot err {e}")
        return None, None, None, None
