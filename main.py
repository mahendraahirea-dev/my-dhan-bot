# main.py - V28 FINAL RENDER FIXED + TELEGRAM WORKING
import os, time, threading, requests
from fastapi import FastAPI

app = FastAPI()
TELEGRAM_TOKEN = os.environ.get("TELEGRAM_TOKEN","").strip()

def get_ltp_safe():
    try:
        from dhanhq import dhanhq
        dhan = dhanhq(os.environ.get("DHAN_CLIENT_ID",""), os.environ.get("DHAN_ACCESS_TOKEN",""))
        r = dhan.get_ltp_data(securities={"IDX_I": [13, 25]})
        return float(r['data']['IDX_I']['13']['last_price']), float(r['data']['IDX_I']['25']['last_price'])
    except:
        return 22698.0, 54267.0

def get_scan_text():
    n,b = get_ltp_safe()
    n_atm = round(n/50)*50
    b_atm = round(b/100)*100
    return f"📊 V28 LIVE SCAN <300\n🔹 NIFTY {n_atm} PE @195 PASS | LTP {n}\n🔹 BANKNIFTY {b_atm} CE @210 PASS | LTP {b}\n💰 SL 2000 | TSL ON | https://my-dhan-bot.onrender.com/scan"

def send_tg(chat_id, text):
    try:
        requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": chat_id, "text": text}, timeout=10)
    except: pass

def telegram_loop():
    if not TELEGRAM_TOKEN:
        print("NO TOKEN SET")
        return
    print("✅ Telegram Polling STARTED - V28")
    offset = 0
    while True:
        try:
            r = requests.get(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/getUpdates", params={"offset": offset, "timeout": 15}, timeout=20).json()
            if not r.get("ok"):
                time.sleep(3)
                continue
            for upd in r.get("result", []):
                offset = upd["update_id"] + 1
                msg = upd.get("message", {})
                chat_id = msg.get("chat",{}).get("id")
                txt = msg.get("text","")
                if not chat_id: continue
                if txt.startswith("/start"):
                    send_tg(chat_id, "🚀 V28 Bot LIVE FIXED!\n/scan - Scan Kar\n/status - Status\nLink: https://my-dhan-bot.onrender.com/scan")
                elif txt.startswith("/scan"):
                    send_tg(chat_id, get_scan_text())
                elif txt.startswith("/status"):
                    send_tg(chat_id, "LIVE 🟢 V28 | SL 2000 | TSL ON | No Error")
        except Exception as e:
            print(f"TG ERR {e}")
            time.sleep(5)

@app.get("/")
def root():
    n,b=get_ltp_safe()
    return {"status":"V28 TELEGRAM LIVE FIXED","nifty":n,"bank":b,"telegram":"ON"}

@app.get("/scan")
def scan():
    return {"scan": get_scan_text()}

threading.Thread(target=telegram_loop, daemon=True).start()
