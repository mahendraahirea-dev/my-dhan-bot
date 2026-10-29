# main.py - V33 MULTI PAPER FINAL - NO PYTZ
import os, time, threading, requests
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

def get_dhan():
    try:
        from dhanhq import dhanhq
        return dhanhq(DHAN_ID, DHAN_TOKEN)
    except: return None

def send_all(text):
    for cid in list(CHAT_IDS):
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=8)
        except: pass

def send_one(cid, text):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=15)
    except: pass

def get_spot_price(underlying):
    try:
        dhan = get_dhan()
        mapping = {"NIFTY":13,"BANKNIFTY":25,"SENSEX":51,"RELIANCE":2885,"HDFCBANK":1333}
        sid = mapping.get(underlying,13)
        try:
            r = dhan.get_ltp_data(securities={"IDX_I": [sid]})
            return float(r['data']['IDX_I'][str(sid)]['last_price'])
        except:
            r = dhan.get_ltp_data(securities={"NSE_EQ": [sid]})
            return float(r['data']['NSE_EQ'][str(sid)]['last_price'])
    except: return 0

def get_option_ltp(underlying, strike, opt_type):
    try:
        dhan = get_dhan()
        exp_list = dhan.get_expiry_list(underlying_symbol=underlying, exchange_segment="NSE_FNO")
        expiry = exp_list['data'][0]
        chain = dhan.get_option_chain(underlying_symbol=underlying, exchange_segment="NSE_FNO", expiry=expiry)
        for o in chain['data']['oc']:
            if int(float(o['strike_price'])) == int(strike) and o['option_type'].upper() == opt_type:
                ltp = float(o.get('last_price', 0) or 0)
                sym = o.get('trading_symbol') or f"{underlying} {strike} {opt_type}"
                return ltp, sym, expiry
        return 0, None, None
    except: return 0, None, None

def get_atm(spot, underlying):
    if underlying in ["NIFTY","SENSEX"]: return round(spot/50)*50
    elif underlying=="BANKNIFTY": return round(spot/100)*100
    else: return round(spot/10)*10

def paper_multi_loop():
    print("📝 V33 MULTI PAPER STARTED - NIFTY BANK SENSEX REL HDFC - NO PYTZ")
    while True:
        try:
            now = datetime.now(IST)
            cur_time = now.time()
            if cur_time < dtime(9,15) or cur_time > dtime(15,20):
                time.sleep(60); continue
            if not AUTO_TRADING: time.sleep(20); continue
            for underlying in SYMBOLS:
                spot = get_spot_price(underlying)
                if spot==0: continue
                atm = get_atm(spot, underlying)
                if underlying not in CURRENT_POSITIONS:
                    for opt_type in ["PE","CE"]:
                        ltp, sym, exp = get_option_ltp(underlying, atm, opt_type)
                        if 15 < ltp < 300 and sym:
                            qty = 50 if underlying=="NIFTY" else 15 if underlying=="BANKNIFTY" else 10 if underlying=="SENSEX" else 250 if underlying=="RELIANCE" else 150
                            pos = {"underlying":underlying,"symbol":sym,"buy_price":ltp,"buy_time":now.strftime('%Y-%m-%d %H:%M:%S'),"buy_spot":spot,"qty":qty,"highest":ltp,"sl_price":ltp-(2000/qty),"strike":atm,"type":opt_type,"expiry":exp}
                            CURRENT_POSITIONS[underlying]=pos
                            send_all(f"📝 PAPER ENTRY {underlying}\n⏰ {pos['buy_time']}\n📈 {sym}\n💰 Prem {ltp} Spot {spot} ATM {atm}\nQty {qty} SL {pos['sl_price']:.1f}\n⚠️ PAPER ONLY")
                            TODAY_TRADES.append({"date":now.strftime('%Y-%m-%d'),"underlying":underlying,"action":"BUY","time":pos['buy_time'],"symbol":sym,"strike":atm,"spot":spot,"premium":ltp,"qty":qty})
                            break
                else:
                    pos = CURRENT_POSITIONS[underlying]
                    curr_ltp,_,_ = get_option_ltp(pos['underlying'], pos['strike'], pos['type'])
                    if curr_ltp==0: continue
                    if curr_ltp > pos['highest']:
                        pos['highest']=curr_ltp
                        pos['sl_price']=max(pos['sl_price'], pos['highest']-(2000/pos['qty']))
                        CURRENT_POSITIONS[underlying]=pos
                    pnl=(curr_ltp-pos['buy_price'])*pos['qty']
                    should=False; reason=""
                    if curr_ltp <= pos['sl_price']: should=True; reason=f"SL HIT {curr_ltp:.1f}"
                    elif cur_time >= dtime(15,15): should=True; reason="TIME 15:15"
                    elif pnl >= 5000: should=True; reason=f"TARGET {curr_ltp}"
                    elif pnl <= -2000: should=True; reason=f"LOSS -2000 {curr_ltp}"
                    if should:
                        et=now.strftime('%Y-%m-%d %H:%M:%S')
                        send_all(f"📕 PAPER EXIT {underlying}\n{pos['buy_time'][11:]}->{et[11:]}\n{pos['symbol']}\n{pos['buy_price']}->{curr_ltp} P&L {pnl:.0f}\n{reason}\nPAPER")
                        TODAY_TRADES.append({"date":now.strftime('%Y-%m-%d'),"underlying":underlying,"action":"SELL","entry_time":pos['buy_time'],"exit_time":et,"symbol":pos['symbol'],"buy":pos['buy_price'],"sell":curr_ltp,"pnl":pnl,"reason":reason})
                        del CURRENT_POSITIONS[underlying]
                time.sleep(2)
            time.sleep(10)
        except Exception as e:
            print(f"ERR {e}"); time.sleep(20)

def tg_loop():
    print("✅ Telegram V33 MULTI NO PYTZ")
    offset=0
    while True:
        try:
            r=requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", params={"offset":offset,"timeout":15}, timeout=20).json()
            if not r.get("ok"): time.sleep(3); continue
            for upd in r.get("result",[]):
                offset=upd["update_id"]+1
                msg=upd.get("message",{})
                cid=msg.get("chat",{}).get("id")
                txt=msg.get("text","")
                if not cid: continue
                CHAT_IDS.add(cid)
                if txt.startswith("/start"):
                    send_one(cid,"📝 V33 MULTI PAPER LIVE!\nNO REAL MONEY\nSymbols: NIFTY BANK SENSEX REL HDFC\n/today /pos /status /auto_on")
                elif txt.startswith("/today"):
                    today_str=datetime.now(IST).strftime('%Y-%m-%d')
                    today_list=[t for t in TODAY_TRADES if today_str in t.get('date','') or today_str in t.get('exit_time','') or today_str in t.get('time','')]
                    total=sum([t.get('pnl',0) for t in today_list if t.get('action')=='SELL'])
                    out=f"📅 AAJ {today_str} P&L {total:.0f} PAPER\n" + "\n".join([f"{t['underlying']} {t['action']} {t.get('symbol','')} {t.get('premium','') or t.get('pnl','')}" for t in today_list[-20:]]) if today_list else "Aaj trade nahi"
                    send_one(cid,out)
                elif txt.startswith("/pos"):
                    send_one(cid, str(CURRENT_POSITIONS) if CURRENT_POSITIONS else "No Position")
                elif txt.startswith("/status"):
                    total=sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
                    send_one(cid,f"V33 MULTI PAPER\nAUTO:{AUTO_TRADING}\nPOS:{list(CURRENT_POSITIONS.keys())}\nTotal P&L:{total:.0f} PAPER")
                elif txt.startswith("/auto_on"): AUTO_TRADING=True; send_one(cid,"AUTO ON")
                elif txt.startswith("/auto_off"): AUTO_TRADING=False; send_one(cid,"AUTO OFF")
        except: time.sleep(5)

@app.get("/")
def root():
    total=sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
    return {"status":"V33 MULTI PAPER NO PYTZ LIVE","positions":CURRENT_POSITIONS,"total_pnl":total}

import threading
threading.Thread(target=tg_loop, daemon=True).start()
threading.Thread(target=paper_multi_loop, daemon=True).start()
