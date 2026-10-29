# main.py - V33 MULTI SYMBOL PAPER - FINAL
import os, time, threading, requests, json
from fastapi import FastAPI
from datetime import datetime, time as dtime
import pytz

app = FastAPI()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()
DHAN_ID = os.environ.get("DHAN_CLIENT_ID","").strip()
DHAN_TOKEN = os.environ.get("DHAN_ACCESS_TOKEN","").strip()

IST = pytz.timezone('Asia/Kolkata')
AUTO_TRADING = True
CHAT_IDS = set()
TODAY_TRADES = []
CURRENT_POSITIONS = {} # symbol -> pos

# MULTI SYMBOLS
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
        if underlying=="NIFTY": sid=13
        elif underlying=="BANKNIFTY": sid=25
        elif underlying=="SENSEX": sid=51
        elif underlying=="RELIANCE": sid=2885
        elif underlying=="HDFCBANK": sid=1333
        else: sid=13
        # idx for index, eq for stocks - try both
        try:
            r = dhan.get_ltp_data(securities={"IDX_I": [sid]})
            price = float(r['data']['IDX_I'][str(sid)]['last_price'])
        except:
            r = dhan.get_ltp_data(securities={"NSE_EQ": [sid]})
            price = float(r['data']['NSE_EQ'][str(sid)]['last_price'])
        return price
    except:
        return 0

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
    except Exception as e:
        print(f"OPT ERR {underlying} {e}")
        return 0, None, None

def get_atm(spot, underlying):
    if underlying in ["NIFTY","SENSEX"]:
        return round(spot/50)*50
    elif underlying=="BANKNIFTY":
        return round(spot/100)*100
    else: # RELIANCE, HDFCBANK
        return round(spot/10)*10

def paper_multi_loop():
    global CURRENT_POSITIONS
    print("📝 V33 MULTI PAPER STARTED - NIFTY BANK SENSEX REL HDFC")
    while True:
        try:
            now = datetime.now(IST)
            cur_time = now.time()
            if cur_time < dtime(9,15) or cur_time > dtime(15,20):
                time.sleep(60); continue
            if not AUTO_TRADING:
                time.sleep(20); continue

            for underlying in SYMBOLS:
                spot = get_spot_price(underlying)
                if spot==0: continue
                atm = get_atm(spot, underlying)

                # If no position for this underlying
                if underlying not in CURRENT_POSITIONS:
                    # Try PE and CE both, whichever <300
                    for opt_type in ["PE","CE"]:
                        ltp, sym, exp = get_option_ltp(underlying, atm, opt_type)
                        if 15 < ltp < 300 and sym:
                            qty = 50 if underlying=="NIFTY" else 15 if underlying=="BANKNIFTY" else 25 if underlying=="SENSEX" else 250 if underlying=="RELIANCE" else 150
                            pos = {
                                "underlying": underlying, "symbol": sym, "buy_price": ltp,
                                "buy_time": now.strftime('%Y-%m-%d %H:%M:%S'), "buy_spot": spot,
                                "qty": qty, "highest": ltp, "sl_price": ltp - (2000/qty),
                                "strike": atm, "type": opt_type, "expiry": exp
                            }
                            CURRENT_POSITIONS[underlying] = pos
                            msg = f"📝 PAPER ENTRY {underlying}\n⏰ {pos['buy_time']}\n📈 {sym}\n💰 Premium {ltp}\n📊 Spot {spot} ATM {atm}\n🔢 Qty {qty}\n🛡️ SL {pos['sl_price']:.1f} (2000 Rs)\nExp {exp}\n⚠️ PAPER ONLY"
                            send_all(msg)
                            TODAY_TRADES.append({"date":now.strftime('%Y-%m-%d'),"underlying":underlying,"action":"BUY","time":pos['buy_time'],"symbol":sym,"strike":atm,"spot":spot,"premium":ltp,"qty":qty,"sl":pos['sl_price']})
                            break
                            time.sleep(2)
                else:
                    # Check exit for this underlying
                    pos = CURRENT_POSITIONS[underlying]
                    curr_ltp, _, _ = get_option_ltp(pos['underlying'], pos['strike'], pos['type'])
                    if curr_ltp==0: continue
                    if curr_ltp > pos['highest']:
                        pos['highest'] = curr_ltp
                        pos['sl_price'] = max(pos['sl_price'], pos['highest'] - (2000/pos['qty']))
                        CURRENT_POSITIONS[underlying] = pos

                    buy = pos['buy_price']
                    pnl = (curr_ltp - buy) * pos['qty']
                    sl = pos['sl_price']

                    should_exit=False
                    reason=""
                    if curr_ltp <= sl:
                        should_exit=True; reason=f"🛑 SL HIT {curr_ltp} SL {sl:.1f}"
                    elif cur_time >= dtime(15,15):
                        should_exit=True; reason="⏰ TIME 15:15"
                    elif pnl >= 5000:
                        should_exit=True; reason=f"🎯 TARGET +5000 {curr_ltp}"
                    elif pnl <= -2000:
                        should_exit=True; reason=f"🛑 LOSS -2000 {curr_ltp}"

                    if should_exit:
                        exit_time = now.strftime('%Y-%m-%d %H:%M:%S')
                        msg = f"📕 PAPER EXIT {underlying}\n⏰ {pos['buy_time'][11:]} -> {exit_time[11:]}\n📈 {pos['symbol']}\n💰 {buy} -> {curr_ltp}\nP&L {pnl:.0f} Rs\n{reason}\nHigh {pos['highest']}\n⚠️ PAPER"
                        send_all(msg)
                        TODAY_TRADES.append({"date":now.strftime('%Y-%m-%d'),"underlying":underlying,"action":"SELL","entry_time":pos['buy_time'],"exit_time":exit_time,"symbol":pos['symbol'],"buy":buy,"sell":curr_ltp,"pnl":pnl,"reason":reason,"highest":pos['highest'],"qty":pos['qty']})
                        del CURRENT_POSITIONS[underlying]

                time.sleep(3) # per symbol gap

            time.sleep(10)
        except Exception as e:
            print(f"MULTI ERR {e}"); time.sleep(20)

def tg_loop():
    global AUTO_TRADING
    print("✅ Telegram V33 MULTI")
    offset=0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", params={"offset": offset, "timeout": 15}, timeout=20).json()
            if not r.get("ok"): time.sleep(3); continue
            for upd in r.get("result", []):
                offset = upd["update_id"]+1
                msg = upd.get("message",{})
                cid = msg.get("chat",{}).get("id")
                txt = msg.get("text","")
                if not cid: continue
                CHAT_IDS.add(cid)
                if txt.startswith("/start"):
                    send_one(cid, "📝 V33 MULTI PAPER LIVE!\n⚠️ NO REAL MONEY\n\nSymbols: NIFTY BANKNIFTY SENSEX RELIANCE HDFC\n✅ Premium <300\n🛡️ SL 2000\n⏰ Auto 15:15\n\n/today - Aajcha Purna Hisab\n/pos - Saglya Position\n/status\n/history\n/auto_on\n/auto_off")
                elif txt.startswith("/today"):
                    today_str = datetime.now(IST).strftime('%Y-%m-%d')
                    today_list = [t for t in TODAY_TRADES if today_str in t.get('date','') or today_str in t.get('time','') or today_str in t.get('exit_time','')]
                    if not today_list:
                        send_one(cid, f"📅 Aaj {today_str} kahi trade nahi - Market band kinva Premium >300")
                    else:
                        total = sum([t.get('pnl',0) for t in today_list if t.get('action')=='SELL'])
                        out = f"📅 AAJCHA HISAB {today_str} MULTI\nTotal P&L {total:.0f} PAPER\n{'='*20}\n"
                        for t in today_list:
                            if t['action']=='BUY':
                                out+=f"\n🟢 {t['underlying']} BUY {t['time'][11:]} {t['symbol']} Premium {t['premium']} Spot {t['spot']}"
                            else:
                                out+=f"\n🔴 {t['underlying']} SELL {t['exit_time'][11:]} {t['symbol']} {t['buy']}->{t['sell']} P&L {t['pnl']:.0f} {t['reason']}"
                        out+=f"\n\n💰 TOTAL: {total:.0f} PAPER\nSymbols: {', '.join(SYMBOLS)}"
                        send_one(cid, out)
                elif txt.startswith("/pos"):
                    if not CURRENT_POSITIONS:
                        send_one(cid, "No Position - All Waiting Premium <300\nSymbols: NIFTY BANK SENSEX REL HDFC")
                    else:
                        out="📊 PAPER POSITIONS:\n"
                        for u,p in CURRENT_POSITIONS.items():
                            out+=f"\n{u}: {p['symbol']} BUY {p['buy_price']} High {p['highest']} SL {p['sl_price']:.1f}"
                        send_one(cid, out)
                elif txt.startswith("/status"):
                    total = sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
                    send_one(cid, f"📝 V33 MULTI PAPER\nAUTO:{AUTO_TRADING}\nPOS:{len(CURRENT_POSITIONS)} {list(CURRENT_POSITIONS.keys())}\nTotal P&L:{total:.0f} PAPER\nMode: NO REAL MONEY - ONLY LIVE LTP\nSymbols: NIFTY BANK SENSEX REL HDFC")
                elif txt.startswith("/history"):
                    total = sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
                    out=f"History {len(TODAY_TRADES)} Total {total:.0f} PAPER\nLast 20:\n"
                    for t in TODAY_TRADES[-20:]:
                        out+=f"{t.get('underlying')} {t['action']} {t.get('symbol')} {t.get('premium') or t.get('pnl')}\n"
                    send_one(cid, out)
                elif txt.startswith("/auto_on"):
                    AUTO_TRADING=True; send_one(cid,"✅ MULTI AUTO ON - Updates Yetil")
                elif txt.startswith("/auto_off"):
                    AUTO_TRADING=False; send_one(cid,"⛔ AUTO OFF")
        except Exception as e:
            print(f"TG ERR {e}"); time.sleep(5)

@app.get("/")
def root():
    total = sum([t.get('pnl',0) for t in TODAY_TRADES if t.get('action')=='SELL'])
    return {"status":"V33 MULTI PAPER","mode":"NO REAL MONEY ONLY PAPER LIVE LTP","symbols":SYMBOLS,"positions":CURRENT_POSITIONS,"total_pnl":total,"today_count":len(TODAY_TRADES)}

threading.Thread(target=tg_loop, daemon=True).start()
threading.Thread(target=paper_multi_loop, daemon=True).start()
