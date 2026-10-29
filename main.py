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
    except: return None

def send_all(text):
    for cid in list(CHAT_IDS):
        try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=10)
        except: pass

def send_one(cid, text):
    try: requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": cid, "text": text}, timeout=15)
    except: pass

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
    except: return 0

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
    except: return 0, None, None

def get_atm(spot, underlying):
    try:
        if underlying in ["NIFTY","SENSEX"]: return int(round(spot/50)*50)
        elif underlying=="BANKNIFTY": return int(round(spot/100)*100)
        else: return int(round(spot/5)*5)
    except: return int(spot)

def paper_multi_loop():
    print("📝 V33.1 MULTI PAPER STARTED")
    while True:
        try:
            now = datetime.now(IST)
            cur_time = now.time()
            if cur_time < dtime(9,15) or cur_time > dtime(15,20):
                time.sleep(60); continue
            if not AUTO_TRADING:
                time.sleep(15); continue
            for underlying in SYMBOLS:
                try:
                    spot = get_spot_price(underlying)
                    if spot==0: time.sleep(1); continue
                    atm = get_atm(spot, underlying)
                    if underlying not in CURRENT_POSITIONS:
                        for opt_type in ["PE","CE"]:
                            ltp, sym, exp = get_option_ltp(underlying, atm, opt_type)
                            if 10 < ltp < 350 and sym:
                                qty = 75 if underlying=="NIFTY" else 30 if underlying=="BANKNIFTY" else 20 if underlying=="SENSEX" else 250
                                sl = max(5, ltp - (2000/qty))
                                pos = {"underlying":underlying,"symbol":sym,"buy_price":ltp,"buy_time":now.strftime('%Y-%m-%d %H:%M:%S'),"buy_spot":spot,"qty":qty,"highest":ltp,"sl_price":sl,"strike":atm,"type":opt_type,"expiry":exp}
                                CURRENT_POSITIONS[underlying]=pos
                                send_all(f"📝 PAPER BUY {underlying}\n⏰ {pos['buy_time']}\n📈 {sym}\n💰 {ltp:.1f} Spot {spot:.1f}\nQty {qty} SL {sl:.1f}\n⚠️ PAPER ONLY")
                                TODAY_TRADES.append({"date":now.strftime('%Y-%m-%d'),"underlying":underlying,"action":"BUY","time":pos['buy_time'],"symbol":sym,"premium":ltp,"qty":qty})
                                break
                    else:
                        pos = CURRENT_POSITIONS[underlying]
                        curr_ltp,_,_ = get_option_ltp(pos['underlying'], pos['strike'], pos['type'])
                        if curr_ltp==0: continue
                        if curr_ltp > pos['highest']:
                            pos['highest']=curr_ltp
                            new_sl = pos['highest'] - (2000/pos['qty'])
                            if new_sl > pos['sl_price']: pos['sl_price']=new_sl
                            CURRENT_POSITIONS[underlying]=pos
                        pnl=(curr_ltp-pos['buy_price'])*pos['qty']
                        should=False; reason=""
                        if curr_ltp <= pos['sl_price']: should=True; reason=f"SL {curr_ltp:.1f}"
                        elif cur_time >= dtime(15,15): should=True; reason="TIME 15:15"
                        elif pnl >= 5000: should=True; reason=f"TARGET {pnl:.0f}"
                        elif pnl <= -2000: should=True; reason=f"LOSS {pnl:.0f}"
                        if should:
                            et=now.strftime('%Y-%m-%d %H:%M:%S')
                            send_all(f"📕 PAPER EXIT {underlying}\n{pos['buy_time'][11:]} -> {et[11:]}\n{pos['symbol']}\nBuy {pos['buy_price']:.1f} -> {curr_ltp:.1f}\nP&L {pnl:.0f} {reason}")
                            TODAY_TRADES.append({"date":now.strftime('%Y-%m-%d'),"underlying":underlying,"action":"SELL","entry_time":pos['buy_time'],"exit_time":et,"symbol":pos['symbol'],"buy":pos['buy_price'],"sell":curr_ltp,"pnl":pnl,"reason":reason})
                            del CURRENT_POSITIONS[underlying]
                    time.sleep(1.5)
                except: time.sleep(1); continue
            time.sleep(8)
        except: time.sleep(10); continue

def tg_loop():
    print("✅ Telegram V33.1 STARTING...")
    try: requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/deleteWebhook?drop_pending_updates=true", timeout=10)
    except: pass
    offset=0
    print("✅ POLLING STARTED")
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", params={"offset":offset,"timeout":25}, timeout=35).json()
            if not r.get("ok"): time.sleep(3); continue
            for upd in r.get("result",[]):
                try:
                    offset = upd["update_id"]+1
                    msg = upd.get("message",{})
                    cid = msg.get("chat",{}).get("id")
                    txt = (msg.get("text","") or "").strip()
                    if not cid: continue
                    CHAT_IDS.add(cid)
                    if txt.startswith("/start"):
                        send_one(cid,"📝 V33.1 MULTI PAPER LIVE!\n✅ NO REAL MONEY\n✅ 100% AUTO\nSymbols: NIFTY BANK SENSEX REL HDFC\n/today /pos /status /auto_on /auto_off")
                    elif txt.startswith("/today"):
                        today_str = datetime.now(IST).strftime('%Y-%m-%d')
                        today_list = [t for t in TODAY_TRADES if today_str in str(t)]
                        total = sum([t.get('pnl',0) for t in today_list if t.get('action')=='SELL'])
                        if not today_list: send_one(cid,f"📅 {today_str}\nAaj trade nahi\nP&L {total:.0f} PAPER")
                        else:
                            lines=[]
                            for t in today_list[-30:]:
                                if t['action']=='BUY': lines.append(f"BUY {t['underlying']} @ {t.get('premium',0):.1f}")
                                else: lines.append(f"SELL {t['underlying']} P&L {t.get('pnl',0):.0f}")
                            send_one(cid,f"📅 AAJ {today_str} P&L {total:.0f} PAPER\n"+"\n".join(lines))
                    elif txt.startswith("/pos"):
                        if not CURRENT_POSITIONS: send_one(cid,"No Open Position")
                        else:
                            out="📊 OPEN:\n"
                            for k,v in CURRENT_POSITIONS.items():
                                curr,_,_=get_option_ltp(v['underlying'], v['strike'], v['type'])
                                pnl=(curr-v['buy_price'])*v['qty'] if curr else 0
                                out+=f"{k} {v['symbol']} Buy {v['buy_price']:.1f} Now {curr:.1f} P&L {pnl:.0f}\n"
                            send_one(cid,out)
                    elif txt.startswith("/status"):
                        total=sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
                        send_one(cid,f"🤖 V33.1 STATUS\nAUTO:{AUTO_TRADING}\nPOS:{list(CURRENT_POSITIONS.keys())}\nP&L:{total:.0f}\nTime:{datetime.now(IST).strftime('%H:%M:%S')}")
                    elif txt.startswith("/auto_on"):
                        globals()['AUTO_TRADING']=True
                        send_one(cid,"✅ AUTO ON")
                    elif txt.startswith("/auto_off"):
                        globals()['AUTO_TRADING']=False
                        send_one(cid,"⏸️ AUTO OFF")
                except: continue
        except: time.sleep(5); continue

@app.get("/")
def root():
    try:
        total=sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
        return {"status":"V33.1 LIVE","auto":AUTO_TRADING,"pos":list(CURRENT_POSITIONS.keys()),"pnl":total}
    except: return {"status":"alive"}

threading.Thread(target=tg_loop, daemon=True).start()
threading.Thread(target=paper_multi_loop, daemon=True).start()
print("🔥 V33.1 THREADS STARTED")
