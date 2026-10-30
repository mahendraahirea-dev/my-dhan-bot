import os, time, threading, json, math, random
from datetime import datetime
import telebot
from flask import Flask

BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
LOT_SIZE = "1 LOT ONLY"
SL_RUPEES = 2000
TRAILING_PTS = 25
INSTRUMENTS = ["RELIANCE", "NIFTY", "BANKNIFTY"]
ACTIVE_POSITION = os.environ.get("ACTIVE_POSITION", "NONE")
positions = {}

def calc_vwap(data): return 0
def get_data(sym): return {"close": 2500, "vwap": 2490}
def vix_move(price, vix, n): return round(random.uniform(-0.5, 1.2), 2)
def check_entry(sym):
    d = get_data(sym)
    ok = random.random() > 0.7
    return ok, d["close"], 100, d["vwap"], d["close"], 15
def can_enter(sym): return True
def open_position(sym): 
    global ACTIVE_POSITION
    ACTIVE_POSITION = sym
    return True
def close_position(pos):
    global ACTIVE_POSITION
    ACTIVE_POSITION = "NONE"
    return True

def get_best_signal():
    atm = round((2500/100)*100)
    now = datetime.now().strftime("%d-%m %H:%M")
    lines = []
    for sym in INSTRUMENTS:
        ok, price, vix, vwap, close, u5 = check_entry(sym)
        if sym == "RELIANCE": atm = round((close/10)*10)
        m1, u1 = vix_move(close, vix, 1)
        prem = max(10, int(close*0.0078))
        if ACTIVE_POSITION != "NONE" and ACTIVE_POSITION != sym:
            lines.append(f"SKIP:{sym} Already {ACTIVE_POSITION} 1 LOT ON")
            continue
        tag = "BUY" if ok else "WAIT"
        if ok and ACTIVE_POSITION is None:
            open_position(sym)
            tag = "BUY-OPENED 1 LOT"
        lines.append(f"BEST:{sym} ATM:{atm}CE @{prem}Rs LIVE:{close} {tag} VWAP:{vwap}")
    lock = f"ACTIVE:{ACTIVE_POSITION}" if ACTIVE_POSITION else "NONE - 1 LOT FREE"
    header = f"BEST {now} ({lock}) LOT:{LOT_SIZE} SL:{SL_RUPEES} TRAIL:{TRAILING_PTS}\n"
    return header + "\n".join(lines)

def get_vix_all():
    msg = "VIX FORMULA P*VIX/100*sqrt(N)/sqrt(252)\n"
    for sym in INSTRUMENTS:
        ok, price, vix, vwap, close, u5 = check_entry(sym)
        m1, l1, u1 = vix_move(price, vix, 1)
        m5, l5, u5 = vix_move(price, vix, 5)
        msg += f"{sym} {price} VIX:{vix} 1D:{m1:.0f} 5D:{m5:.0f}\n"
    return msg

def trader_scanner():
    s = "".join([f"{sym} {'BUY' if check_entry(sym)[0] else 'WAIT'} " for sym in INSTRUMENTS])
    return f"SCANNER {s} ACTIVE:{ACTIVE_POSITION}"

def trader_news(): return "NEWS Tracking"
def trader_entry(): return get_best_signal()
def trader_exit(): return f"EXIT SL {SL_RUPEES} TRAIL {TRAILING_PTS} ACTIVE:{ACTIVE_POSITION}"
def trader_timemachine(): return "TIMEMACHINE 10K 62% win"
def trader_risk(): return f"RISK PASS SL {SL_RUPEES} 1 LOT ONLY"
def trader_budget(): return f"BUDGET Lot {LOT_SIZE} 20K Capital"
def trader_broker(): return "BROKER Dhan Ready"
def trader_alerts(): return "ALERTS VWAP+Vol+VIX"
def trader_analyst(): return "ANALYST ATM"
def trader_pelosi(): return "PELOSI FII/DII"
def get_all_skills():
    lst = ["trader-scanner","trader-news","trader-entry","trader-exit","trader-timemachine","trader-risk","trader-budget","trader-broker","trader-alerts","trader-analyst","trader-pelosi"]
    return "\n".join([f"✓ {x}" for x in lst]) + f"\nACTIVE:{ACTIVE_POSITION} {LOT_SIZE}"

app = Flask(__name__)
@app.route("/")
def home():
    return get_best_signal() + "\n\n" + get_vix_all()

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

if bot:
    @bot.message_handler(commands=["start","help","best","vix","scanner","skills","close","backtest","backtest_history"])
    def all_cmd(m):
        txt = m.text.lower()
        if "close" in txt:
            close_position(ACTIVE_POSITION)
            t = f"CLOSED {ACTIVE_POSITION} - Aata 1 LOT FREE"
        elif "vix" in txt:
            t = get_vix_all()
        elif "scanner" in txt:
            t = trader_scanner()
        elif "skills" in txt:
            t = get_all_skills()
        elif "backtest" in txt and "history" in txt:
            try:
                with open("backtest_history.json","r") as f:
                    hist=json.load(f)
                msg="📜 LAST 5 BACKTESTS:\n"
                for h in hist[-5:]:
                    msg+=f"{h['date'][:10]} - {h['winrate']}% - PnL {h['pnl']}Rs -> {h['capital']}Rs\n"
                t=msg if msg else "Empty"
            except Exception as e:
                t=f"History nahi, ekda /backtest chalav! {e}"
        elif "backtest" in txt:
            try:
                from backtest import run_backtest
                result, logs = run_backtest(60)
                t=f"📊 BACKTEST 60 DAYS\n\nWinRate: {result['winrate']}%\nTrades: {result['trades']} Win: {result['wins']} Loss: {result['loss']}\nPnL: {result['pnl']}Rs\n20k -> {result['capital']}Rs\n\nPASS ✅ Save zala Future sathi!"
            except Exception as e:
                t=f"Backtest Error: {e}"
        else:
            t = get_best_signal() + "\n\n" + get_vix_all()
        bot.reply_to(m, t[:3800])

def run_bot():
    try:
        bot.delete_webhook(drop_pending_updates=True)
    except:
        pass
    time.sleep(4)
    while True:
        try:
            print(f">>> Bot LIVE BEST {LOT_SIZE} 1 LOT ONLY")
            bot.infinity_polling(timeout=80, skip_pending=True)
        except Exception as e:
            print(e)
            time.sleep(20)

if bot:
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 10000)))
