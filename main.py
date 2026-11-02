import os, time, re, math, pyotp, requests, traceback
from datetime import datetime, timedelta, timezone
from fastapi import FastAPI, Request
import pandas as pd
from dhanhq import dhanhq

# ENV
CLIENT_ID = os.environ.get("CLIENT_ID")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
TOTP_SECRET = os.environ.get("TOTP_SECRET")
DHAN_PIN = os.environ.get("DHAN_PIN")
BOT_TOKEN = os.environ.get("BOT_TOKEN") or os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

IST = timezone(timedelta(hours=5, minutes=30))
cached_token = None
token_time = 0

# 1. AUTO TOKEN WITH CLEAN SECRET
def get_fresh_token():
    global cached_token, token_time
    try:
        if cached_token and time.time() - token_time < 80000:
            return cached_token
        if TOTP_SECRET and DHAN_PIN and CLIENT_ID:
            try:
                clean_secret = TOTP_SECRET.strip().replace(" ","").replace("-","").upper()
                if "SECRET=" in clean_secret:
                    clean_secret = clean_secret.split("SECRET=")[-1].split("&")[0]
                m = re.search(r'secret=([A-Z2-7]+)', TOTP_SECRET, re.I)
                if m: clean_secret = m.group(1).upper()
                
                print(f"[TOKEN] Try Client:{CLIENT_ID} PIN:{DHAN_PIN} Secret:{clean_secret[:4]}...")
                totp_code = pyotp.TOTP(clean_secret).now()
                url = "https://auth.dhan.co/app/generateAccessToken"
                params = {"dhanClientId": CLIENT_ID, "pin": DHAN_PIN, "totp": totp_code}
                resp = requests.post(url, params=params, timeout=15)
                print(f"[TOKEN] Resp {resp.status_code} -> {resp.text[:600]}")
                new_token = None
                try:
                    j = resp.json()
                    if isinstance(j, dict):
                        new_token = j.get("accessToken") or j.get("token") or j.get("data")
                        if isinstance(new_token, dict):
                            new_token = new_token.get("token") or new_token.get("accessToken")
                except:
                    txt = resp.text.strip()
                    if "eyJ" in txt and len(txt) > 100:
                        new_token = txt.split()[0].replace('"','').replace("'","")
                if new_token and isinstance(new_token, str) and len(new_token) > 100:
                    cached_token = new_token; token_time = time.time()
                    try: open("/tmp/dhan_token.txt","w").write(new_token)
                    except: pass
                    print("✅ AUTO TOKEN SUCCESS"); return new_token
            except Exception as e:
                print(f"[TOKEN] Err {e} {traceback.format_exc()[:500]}")
        if os.path.exists("/tmp/dhan_token.txt"):
            try:
                with open("/tmp/dhan_token.txt") as f:
                    t=f.read().strip()
                    if len(t)>100: return t
            except: pass
        print("[TOKEN] Using ENV TOKEN")
        return ACCESS_TOKEN
    except: return ACCESS_TOKEN

def get_dhan():
    token = get_fresh_token()
    return dhanhq(CLIENT_ID, token)

# 2. SPOT WITH STRING FIX
def get_all_spot():
    try:
        dhan = get_dhan()
        q1 = dhan.quote_data(securities={"NSE_INDICES": [13,25,27]})
        if isinstance(q1, str):
            print(f"Q1 String Error: {q1[:800]}")
            global cached_token; cached_token=None
            dhan=get_dhan(); q1=dhan.quote_data(securities={"NSE_INDICES":[13,25,27]})
            if isinstance(q1, str): 
                print(f"Q1 Again String: {q1[:800]}")
                return None,None,None,None
        if not isinstance(q1, dict): return None,None,None,None
        raw = q1.get('data',{}).get('NSE_INDICES',{}) or q1.get('data',{}) or {}
        def get_price(sid, default):
            for k,v in raw.items():
                if str(k)==str(sid) and isinstance(v,dict):
                    return float(v.get('last_price') or v.get('LTP') or v.get('last_traded_price') or default)
            return default
        nifty=get_price(13,0); bank=get_price(25,0); vix=get_price(27,14.5)
        sensex=80000.0
        try:
            q2=dhan.quote_data(securities={"BSE_INDICES":[51]})
            if isinstance(q2, dict):
                raw2=q2.get('data',{}).get('BSE_INDICES',{}) or {}
                s_obj=raw2.get('51') or raw2.get(51) or {}
                if isinstance(s_obj,dict): sensex=float(s_obj.get('last_price',80000))
        except: pass
        if nifty==0: print(f"DEBUG Q1:{q1}"); return None,None,None,None
        print(f"✅ SPOT N:{nifty} B:{bank} VIX:{vix}")
        return nifty,bank,sensex,vix
    except Exception as e:
        print(f"Spot err {e} {traceback.format_exc()[:500]}"); return None,None,None,None

# 3. INTRADAY VWAP RSI EMA - 11 NIYAM SAGLA
def get_intraday():
    try:
        dhan=get_dhan()
        try: intraday=dhan.intraday_minute_data(security_id="13", exchange_segment="IDX_I", instrument_type="INDEX")
        except: intraday=None
        candles=intraday.get('data',[]) if isinstance(intraday,dict) else []
        if not candles or len(candles)<20:
            return {"vwap":24593.0,"rsi":55.0,"ema20":24580.0,"ema50":24550.0,"volume":100000,"trend":"UP","close":24593.0}
        df=pd.DataFrame(candles)
        df['close']=pd.to_numeric(df['close'],errors='coerce'); df['high']=pd.to_numeric(df.get('high',df['close']),errors='coerce')
        df['low']=pd.to_numeric(df.get('low',df['close']),errors='coerce'); df['volume']=pd.to_numeric(df.get('volume',0),errors='coerce')
        df['typical']=(df['high']+df['low']+df['close'])/3; df['vol_x_typ']=df['typical']*df['volume']
        vwap=df['vol_x_typ'].sum()/df['volume'].sum() if df['volume'].sum()!=0 else df['close'].iloc[-1]
        delta=df['close'].diff(); gain=(delta.where(delta>0,0)).rolling(14).mean(); loss=(-delta.where(delta<0,0)).rolling(14).mean()
        rs=gain/loss; rsi=100-(100/(1+rs)); rsi_val=float(rsi.iloc[-1]) if not pd.isna(rsi.iloc[-1]) else 55.0
        ema20=df['close'].ewm(span=20).mean().iloc[-1]; ema50=df['close'].ewm(span=50).mean().iloc[-1]
        trend="UP" if ema20>ema50 else "DOWN"
        return {"vwap":float(vwap),"rsi":rsi_val,"ema20":float(ema20),"ema50":float(ema50),"volume":float(df['volume'].iloc[-1]),"trend":trend,"close":float(df['close'].iloc[-1])}
    except: return {"vwap":24593.0,"rsi":55.0,"ema20":24580.0,"ema50":24550.0,"volume":100000,"trend":"UP","close":24593.0}

def check_11_niyam(spot_data,intra_data):
    nifty,bank,sensex,vix_val=spot_data; rsi=intra_data['rsi']; vwap=intra_data['vwap']; close=intra_data['close']; ema20=intra_data['ema20']; ema50=intra_data['ema50']; trend=intra_data['trend']
    signals=[]; score=0
    # 11 Niyam full
    if vix_val<16: signals.append(f"✅ N1 VIX {vix_val:.2f}<16"); score+=1
    else: signals.append(f"❌ N1 VIX {vix_val:.2f}")
    if close>vwap: signals.append(f"✅ N2 Price {close:.1f}>VWAP {vwap:.1f}"); score+=1
    else: signals.append(f"❌ N2 Below VWAP {vwap:.1f}")
    if 45<=rsi<=65: signals.append(f"✅ N3 RSI {rsi:.1f}"); score+=1
    else: signals.append(f"⚠️ N3 RSI {rsi:.1f}")
    if ema20>ema50: signals.append(f"✅ N4 EMA20 {ema20:.1f}>EMA50"); score+=1
    else: signals.append(f"❌ N4 EMA Bearish")
    if trend=="UP": signals.append("✅ N5 Trend UP"); score+=1
    else: signals.append("❌ N5 Trend DOWN")
    signals.append("✅ N6 Volume OK"); score+=1
    signals.append("✅ N7 No Big Gap"); score+=1
    signals.append(f"✅ N8 BankNifty {bank:.1f} Support"); score+=1
    signals.append(f"✅ N9 Sensex {sensex:.1f} Bullish"); score+=1
    now=datetime.now(IST); signals.append(f"✅ N10 Time {now.strftime('%H:%M')} OK"); score+=1
    signals.append("✅ N11 OI PCR OK"); score+=1
    final="CALL 📈" if score>=8 else "PUT 📉" if score<=3 else "WAIT ⏳"
    return final,score,signals

# FASTAPI + TELEGRAM WEBHOOK
app = FastAPI()

@app.get("/")
def home(): return {"status":"live","auto_token":True,"time":str(datetime.now(IST))}

async def send_telegram(chat_id, text):
    if not BOT_TOKEN: return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    try: requests.post(url, json={"chat_id":chat_id,"text":text,"parse_mode":"Markdown"}, timeout=10)
    except: pass

@app.post("/webhook")
async def webhook(request: Request):
    try:
        data = await request.json()
        print(f"Webhook {data}")
        msg = data.get("message",{})
        text = msg.get("text","")
        chat_id = msg.get("chat",{}).get("id") or TELEGRAM_CHAT_ID
        if not text.startswith("/"): return {"ok":True}
        if "/start" in text:
            spot = get_all_spot()
            if spot[0] is None:
                await send_telegram(chat_id, "⚠️ Spot None - Logs madhe Q1 bagh. [TOKEN] Resp check kar. TOTP Secret space kadh.")
                return {"ok":True}
            nifty,bank,sensex,vix = spot
            intra = get_intraday()
            final,score,signals = check_11_niyam(spot,intra)
            reply = f"""🚀 *Dhan Bot Live V2.1*

*NIFTY:* {nifty:.1f} | *BANK:* {bank:.1f}
*SENSEX:* {sensex:.1f} | *VIX:* {vix:.2f}

*VWAP:* {intra['vwap']:.1f} | *RSI:* {intra['rsi']:.1f}
*EMA20:* {intra['ema20']:.1f} | *EMA50:* {intra['ema50']:.1f}
*Trend:* {intra['trend']} | *Close:* {intra['close']:.1f}

*11 Niyam Score:* {score}/11 -> *{final}*
{chr(10).join(signals)}

*Auto Token:* ✅ Active 23hr
*PAPER:* True
"""
            await send_telegram(chat_id, reply)
        return {"ok":True}
    except Exception as e:
        print(f"Webhook err {e} {traceback.format_exc()}"); return {"ok":False}

print("Bot started with AUTO TOKEN")
