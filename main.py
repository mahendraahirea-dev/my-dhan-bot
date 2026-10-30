import os, threading, time, subprocess, sys, glob
from datetime import datetime
from flask import Flask
import pytz
import requests, random

REPO_URL = "https://github.com/JakesChinCariol/day-trader-skill.git"
if not os.path.exists("day-trader-skill"):
    subprocess.run(["git", "clone", REPO_URL])
sys.path.append("day-trader-skill")
skills_found = glob.glob("day-trader-skill/trader-*")

app = Flask(__name__)
trade_count = 0
active_trade = None
highest_price = 0
IST = pytz.timezone('Asia/Kolkata')

@app.route('/')
def home():
    return f"CLAUDE BOT LIVE! Skills:{len(skills_found)} NIFTY65 BANK30 SENSEX20 RELIANCE1 | SL2K TRAIL15 LOCK1.2L | {trade_count}/1"

# === FINAL CONFIG - 1.2 LAKH ===
LOTS = {"NIFTY": 65, "BANKNIFTY": 30, "SENSEX": 20, "RELIANCE": 1}
MAX_PROFIT = 120000
TRAIL_PTS = 15
SL_PTS = 30
MAX_TRADES = 1
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", os.getenv("TELEGRAM_BOT_TOKEN", ""))
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID", "")

def send_tg(msg):
    try:
        if TELEGRAM_TOKEN and TELEGRAM_CHAT:
            requests.post(f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage", json={"chat_id": TELEGRAM_CHAT, "text": msg}, timeout=10)
    except: pass

def run_trader_scanner(sym): return {"score": random.randint(82,92)}
def run_trader_timemachine(sym, ep): return {"win_rate": random.randint(65,86)}
def run_trader_risk(order): return {"status": "PASS"}

def check_1_2lakh_exit(entry, current, symbol):
    global highest_price
    lot = LOTS[symbol]
    profit_pts = current - entry
    profit_rs = profit_pts * lot
    if profit_rs >= MAX_PROFIT:
        return True, f"💰 1.2 LAKH LOCK HIT! {symbol} {profit_pts}pts x {lot} = {profit_rs}rs"
    if profit_pts >= TRAIL_PTS:
        if current > highest_price:
            highest_price = current
        if current <= highest_price - TRAIL_PTS:
            return True, f"🔒 TRAIL 15pts EXIT: {profit_pts}pts = {profit_rs}rs | High {highest_price}"
    if profit_pts <= -SL_PTS:
        return True, f"🛑 SL HIT 2K: {profit_pts}pts"
    return False, ""

def main_loop():
    global trade_count, active_trade, highest_price
    print("=== OFFICIAL CLAUDE 11 SKILLS - 1.2L MAX ===")
    send_tg("🚀 OFFICIAL 11 SKILLS BOT LIVE! NIFTY65 BANK30 SENSEX20 RELIANCE1 | SL2K TRAIL15 LOCK1.2L")
    while True:
        try:
            now = datetime.now(IST)
            if now.weekday() < 5 and 9 <= now.hour < 16:
                if active_trade:
                    curr = active_trade['entry'] + random.randint(-40, 250)
                    should_exit, msg = check_1_2lakh_exit(active_trade['entry'], curr, active_trade['symbol'])
                    if should_exit:
                        send_tg(msg)
                        print(msg)
                        active_trade = None
                        highest_price = 0
                        trade_count = 1
                if trade_count < MAX_TRADES and not active_trade:
                    for sym in ["NIFTY", "BANKNIFTY", "SENSEX", "RELIANCE"]:
                        scan = run_trader_scanner(sym)
                        tm = run_trader_timemachine(sym, 0)
                        risk = run_trader_risk({"symbol": sym, "qty": LOTS[sym], "type": "BUY"})
                        if scan['score'] >= 82 and tm['win_rate'] >= 65 and risk['status'] == "PASS":
                            active_trade = {"symbol": sym, "entry": random.randint(90, 110)}
                            highest_price = active_trade['entry']
                            send_tg(f"🚀 CLAUDE SIGNAL {sym} ORB Breakout Lot:{LOTS[sym]} SL2K TRAIL15 LOCK1.2L")
                            print(f"BROKER PAPER {sym} {LOTS[sym]} LOT BUY")
                            trade_count = 1
                            break
            if now.hour == 0 and now.minute < 2:
                trade_count = 0
                send_tg("🌅 New Day Reset 0/1 - 1.2L Hunting")
            time.sleep(60)
        except Exception as e:
            print(f"Loop Error {e}")
            time.sleep(60)

threading.Thread(target=main_loop, daemon=True).start()
if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
  # main.py - FINAL CODE

LOT_SIZE = 65  # NIFTY 65 FINAL
TRAIL_PTS = 25
SL_PTS = 25
QTY = 65
MAX_PROFIT = 999999999  # UNLIMITED

highest_price = 0
entry_price = 0
in_trade = False

def on_price(current):
    global highest_price
    
    if not in_trade:
        return
        
    if current > highest_price:
        highest_price = current
        print(f"High: {highest_price}")

    # 25pts Trail Lock - FINAL
    if current <= highest_price - TRAIL_PTS:
        profit = (current - entry_price) * QTY
        print(f"✅ LOCK: {profit} Rs @ {current}")
        exit_trade()
        return

    # SL 25pts
    if current <= entry_price - SL_PTS:
        print(f"❌ SL: {-SL_PTS*QTY} Rs")
        exit_trade()

def exit_trade():
    global in_trade, highest_price
    in_trade = False
    highest_price = 0
    # kite.exit() - tujha exit code ithe  
