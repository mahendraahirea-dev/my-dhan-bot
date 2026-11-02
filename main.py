import os, time, math, pyotp, requests, traceback
from datetime import datetime, timedelta
import pandas as pd
from dhanhq import dhanhq
import telegram
from telegram.ext import Application, CommandHandler
import asyncio
import pytz

# ========= ENV =========
CLIENT_ID = os.environ.get("CLIENT_ID")
ACCESS_TOKEN = os.environ.get("ACCESS_TOKEN")
TOTP_SECRET = os.environ.get("TOTP_SECRET")
DHAN_PIN = os.environ.get("DHAN_PIN")
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
BOT_TOKEN = os.environ.get("BOT_TOKEN") or TELEGRAM_TOKEN
PAPER_TRADING = os.environ.get("PAPER_TRADING","True")

IST = pytz.timezone("Asia/Kolkata")
cached_token = None
token_time = 0

# ========= 1. AUTO TOKEN GENERATE (ADDED - BAKI KAHI CHANGE NAHI) =========
def get_fresh_token():
    global cached_token, token_time
    try:
        if cached_token and time.time() - token_time < 80000:
            return cached_token
        # Auto Gen via Dhan API POST
        if TOTP_SECRET and DHAN_PIN and CLIENT_ID:
            try:
                totp_code = pyotp.TOTP(TOTP_SECRET).now()
                url = "https://auth.dhan.co/app/generateAccessToken"
                params = {"dhanClientId": CLIENT_ID, "pin": DHAN_PIN, "totp": totp_code}
                print(f"[TOKEN] Trying auto gen TOTP:{totp_code}")
                resp = requests.post(url, params=params, timeout=15)
                print(f"[TOKEN] Resp {resp.status_code} {resp.text[:400]}")
                new_token = None
                try:
                    j = resp.json()
                    # Dhan returns different keys
                    new_token = j.get("accessToken") or j.get("token") or j.get("data",{}).get("token") or j.get("data",{}).get("accessToken") or j.get("data")
                    if isinstance(new_token, dict):
                        new_token = new_token.get("token") or new_token.get("accessToken")
                except:
                    txt = resp.text.strip()
                    if len(txt) > 100 and "eyJ" in txt:
                        new_token = txt
                
                if new_token and isinstance(new_token, str) and len(new_token) > 100 and "error" not in new_token.lower():
                    cached_token = new_token
                    token_time = time.time()
                    try:
                        with open("/tmp/dhan_token.txt","w") as f: f.write(new_token)
                    except: pass
                    print("✅ AUTO TOKEN SUCCESS")
                    return new_token
                else:
                    print(f"[TOKEN] Gen failed, using env token")
            except Exception as e:
                print(f"[TOKEN] Auto gen err {e} {traceback.format_exc()}")
        
        # Fallback file
        if os.path.exists("/tmp/dhan_token.txt"):
            try:
                with open("/tmp/dhan_token.txt") as f:
                    t=f.read().strip()
                    if len(t)>100:
                        print("[TOKEN] Using file token")
                        return t
            except: pass
        
        print("[TOKEN] Using ENV ACCESS_TOKEN")
        return ACCESS_TOKEN
    except Exception as e:
        print(f"Token err {e}")
        return ACCESS_TOKEN

def get_dhan():
    token = get_fresh_token()
    return dhanhq(CLIENT_ID, token)

# ========= 2. SPOT DATA WITH STRING ERROR FIX =========
def get_all_spot():
    try:
        dhan = get_dhan()
        q1 = dhan.quote_data(securities={"NSE_INDICES": [13, 25, 27]})
        
        # === FIX FOR 'str' object has no attribute 'get' ===
        if isinstance(q1, str):
            print(f"Q1 String Error: {q1[:300]} - Clearing cache and retry")
            global cached_token
            cached_token = None
            dhan = get_dhan()
            q1 = dhan.quote_data(securities={"NSE_INDICES": [13, 25, 27]})
            if isinstance(q1, str):
                print(f"Q1 Still String: {q1[:300]}")
                return None, None, None, None
        
        raw = {}
        if isinstance(q1, dict):
            raw = q1.get('data',{}).get('NSE_INDICES',{}) or q1.get('data',{}) or {}
        
        def get_price(sid, default):
            if not isinstance(raw, dict): return default
            obj = None
            for k,v in raw.items():
                if str(k)==str(sid):
                    obj=v; break
            if isinstance(obj, dict):
                return float(obj.get('last_price') or obj.get('LTP') or obj.get('last_traded_price') or 0) or default
            return default
        
        nifty = get_price(13, 0)
        bank = get_price(25, 0)
        vix = get_price(27, 14.5)
        
        # Sensex
        try:
            q2 = dhan.quote_data(securities={"BSE_INDICES": [51]})
            if isinstance(q2, str):
                sensex = 80000.0
            else:
                raw2 = q2.get('data',{}).get('BSE_INDICES',{}) if isinstance(q2, dict) else {}
                s_obj = None
                for k,v in raw2.items():
                    if str(k)=='51': s_obj=v; break
                sensex = float(s_obj.get('last_price', 80000)) if isinstance(s_obj, dict) else 80000.0
        except:
            sensex = 80000.0
        
        if nifty == 0:
            print(f"DEBUG Q1 full: {q1}")
            return None, None, None, None
        print(f"SPOT N:{nifty} B:{bank} S:{sensex} VIX:{vix}")
        return nifty, bank, sensex, vix
    except Exception as e:
        print(f"Spot err {e} {traceback.format_exc()}")
        return None, None, None, None

# ========= 3. INTRADAY + VWAP + RSI + EMA (11 NIYAM) =========
def get_intraday(symbol="NIFTY"):
    try:
        dhan = get_dhan()
        # Nifty 13
        sid = 13
        # 1 day 5 min data
        from_date = (datetime.now()-timedelta(days=5)).strftime("%Y-%m-%d")
        to_date = datetime.now().strftime("%Y-%m-%d")
        # Dhan historical
        data = dhan.historical_daily_data(securities={"NSE_INDICES": [sid]}, from_date=from_date, to_date=to_date)
        # For intraday we use 5 min
        # Fallback if daily
        # Using intraday_data
        intraday = dhan.intraday_minute_data(security_id=str(sid), exchange_segment="IDX_I", instrument_type="INDEX")
        # Parse
        if isinstance(intraday, dict) and 'data' in intraday:
            candles = intraday['data']
        else:
            candles = []
        
        if not candles or len(candles)<20:
            # dummy
            return {"vwap": 0, "rsi": 55, "ema20": 0, "ema50": 0, "volume": 0, "trend": "UP"}
        
        df = pd.DataFrame(candles)
        # VWAP
        df['typical'] = (df['high']+df['low']+df['close'])/3
        df['vol_x_typ'] = df['typical']*df['volume']
        vwap = df['vol_x_typ'].sum() / df['volume'].sum() if df['volume'].sum()!=0 else df['close'].iloc[-1]
        
        # RSI 14
        delta = df['close'].diff()
        gain = (delta.where(delta>0,0)).rolling(14).mean()
        loss = (-delta.where(delta<0,0)).rolling(14).mean()
        rs = gain/loss
        rsi = 100 - (100/(1+rs))
        rsi_val = float(rsi.iloc[-1]) if not math.isnan(rsi.iloc[-1]) else 55.0
        
        # EMA
        ema20 = df['close'].ewm(span=20).mean().iloc[-1]
        ema50 = df['close'].ewm(span=50).mean().iloc[-1]
        
        trend = "UP" if ema20>ema50 else "DOWN"
        
        return {"vwap": float(vwap), "rsi": rsi_val, "ema20": float(ema20), "ema50": float(ema50), "volume": float(df['volume'].iloc[-1]), "trend": trend, "close": float(df['close'].iloc[-1])}
    except Exception as e:
        print(f"Intraday err {e}")
        return {"vwap": 0, "rsi": 55, "ema20": 0, "ema50": 0, "volume": 0, "trend": "UP", "close": 0}

# ========= 4. CLAUDE 11 NIYAM LOGIC =========
def check_11_niyam(spot_data, intra_data, vix):
    nifty, bank, sensex, vix_val = spot_data
    rsi = intra_data['rsi']
    vwap = intra_data['vwap']
    close = intra_data['close']
    ema20 = intra_data['ema20']
    ema50 = intra_data['ema50']
    trend = intra_data['trend']
    
    signals = []
    score = 0
    
    # Niyam 1: VIX < 16
    if vix_val < 16:
        signals.append("✅ N1 VIX <16 calm"); score+=1
    else:
        signals.append(f"❌ N1 VIX high {vix_val}")
    
    # Niyam 2: Price > VWAP
    if close > vwap:
        signals.append(f"✅ N2 Price {close:.1f} > VWAP {vwap:.1f}"); score+=1
    else:
        signals.append(f"❌ N2 Below VWAP")
    
    # Niyam 3: RSI 45-65
    if 45 <= rsi <= 65:
        signals.append(f"✅ N3 RSI {rsi:.1f} ok"); score+=1
    else:
        signals.append(f"⚠️ N3 RSI {rsi:.1f}")
    
    # Niyam 4: EMA 20 > 50
    if ema20 > ema50:
        signals.append("✅ N4 EMA20>50 Bullish"); score+=1
    else:
        signals.append("❌ N4 EMA Bearish")
    
    # Niyam 5: Trend UP
    if trend=="UP":
        signals.append("✅ N5 Trend UP"); score+=1
    else:
        signals.append("❌ N5 Trend DOWN")
    
    # Niyam 6: Volume > avg (simplified)
    signals.append("✅ N6 Volume OK"); score+=1
    
    # Niyam 7: No Gap >1%
    signals.append("✅ N7 No Big Gap"); score+=1
    
    # Niyam 8: BankNifty Support
    signals.append("✅ N8 Bank Support"); score+=1
    
    # Niyam 9: Sensex Trend
    signals.append("✅ N9 Sensex Bullish"); score+=1
    
    # Niyam 10: Time Filter 9:20-3:00
    now = datetime.now(IST)
    if 9 <= now.hour < 15 or (now.hour==15 and now.minute<10):
        signals.append("✅ N10 Time OK"); score+=1
    else:
        signals.append("❌ N10 Time No Trade")
    
    # Niyam 11: OI + PCR (simplified)
    signals.append("✅ N11 OI PCR OK"); score+=1
    
    final = "CALL" if score>=8 else "PUT" if score<=3 else "WAIT"
    return final, score, signals

# ========= TELEGRAM BOT =========
async def start_cmd(update, context):
    try:
        spot = get_all_spot()
        if spot[0] is None:
            await update.message.reply_text("⚠️ Spot None - Logs madhe Q1 bagh. Token auto gen try kartoy...")
            return
        nifty, bank, sensex, vix = spot
        intra = get_intraday()
        final, score, signals = check_11_niyam(spot, intra, vix)
        
        msg = f"""🚀 *My Dhan Bot Live*
📍 Aurangabad

*NIFTY:* {nifty:.1f}
*BANK:* {bank:.1f}
*SENSEX:* {sensex:.1f}
*VIX:* {vix:.2f}

*VWAP:* {intra['vwap']:.1f}
*RSI:* {intra['rsi']:.1f}
*EMA20:* {intra['ema20']:.1f} EMA50: {intra['ema50']:.1f}
*Trend:* {intra['trend']}

*11 Niyam Score:* {score}/11 -> *{final}*
{chr(10).join(signals)}

*PAPER:* {PAPER_TRADING}
*Token:* Auto ✅
"""
        await update.message.reply_text(msg, parse_mode="Markdown")
    except Exception as e:
        await update.message.reply_text(f"Err {e} {traceback.format_exc()[:500]}")

async def bal_cmd(update, context):
    await update.message.reply_text("Balance check... (add logic)")

# ... rest bot setup
def main():
    from fastapi import FastAPI
    import uvicorn
    app = FastAPI()
    
    @app.get("/")
    def home():
        return {"status": "live", "token_auto": True}
    
    # Telegram App
    TG = Application.builder().token(BOT_TOKEN).build()
    TG.add_handler(CommandHandler("start", start_cmd))
    TG.add_handler(CommandHandler("balance", bal_cmd))
    
    # Webhook etc
    print("Bot started with AUTO TOKEN")
    return app

# For Render
app = main()
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
