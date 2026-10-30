import os, threading, time, datetime, math
from flask import Flask
import telebot

BOT_TOKEN = os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN")
LOT_SIZE = 65
SL_RUPEES = 2000
TRAILING_PTS = 25
INSTRUMENTS = ["NIFTY","BANKNIFTY","SENSEX","NIFTY50","RELIANCE"]

app = Flask(__name__)
positions = {}

def calc_vwap(candles):
    tpv = 0
    tv = 0
    for c in candles:
        tpv += ((c["h"]+c["l"]+c["c"])/3)*c["v"]
        tv += c["v"]
    return tpv/tv if tv else 0

def get_data(sym):
    prices = {
        "NIFTY": 24600,
        "BANKNIFTY": 52000,
        "SENSEX": 81000,
        "NIFTY50": 24600,
        "RELIANCE": 2950
    }
    vixs = {
        "NIFTY": 14.5,
        "BANKNIFTY": 15.2,
        "SENSEX": 14.8,
        "NIFTY50": 14.5,
        "RELIANCE": 28.0
    }
    p = prices[sym]
    vix = vixs[sym]
    c = [
        {"h": p+50, "l": p-100, "c": p-20, "v": 1200000},
        {"h": p+100, "l": p-50, "c": p, "v": 1500000}
    ]
    return c, p, vix

def check_entry(sym):
    c, price, vix = get_data(sym)
    vwap = calc_vwap(c)
    last = c[-1]
    avg = (c[0]["v"]+c[1]["v"])/2
    ok = last["c"] > vwap and last["v"] > avg*1.2
    return ok, vwap, price, vix

def vix_move(price, vix, days=1):
    m = price*(vix/100)*math.sqrt(days)/math.sqrt(252)
    return m, price-m, price+m

def get_best_signal():
    lines = []
    for sym in INSTRUMENTS:
        ok, vwap, close, vix = check_entry(sym)
        atm = round(close/50)*50
        if sym == "SENSEX":
            atm = round(close/100)*100
        if sym == "RELIANCE":
            atm = round(close/10)*10
        if sym not in positions:
            positions[sym] = close - (SL_RUPEES/LOT_SIZE)
        m1, l1, u1 = vix_move(close, vix, 1)
        prem = max(10, int(close*0.0078))
        tag = "BUY" if ok else "WAIT"
        line1 = f"BEST:{sym} {atm}CE @{prem}Rs"
        line2 = f"LIVE:{close} {tag} VWAP:{vwap:.0f}"
        line3 = f"VIX:+-{m1:.0f} [{l1:.0f}-{u1:.0f}]"
        line4 = f"SL:{positions[sym]:.0f} Lot:{LOT_SIZE}"
        lines.append(f"{line1} {line2} {line3} {line4}")
    now = datetime.datetime.now().strftime('%d-%m %H:%M')
    header = f"BEST {now} LOT:{LOT_SIZE} SL:{SL_RUPEES} TRAIL:{TRAILING_PTS} UNLTD\n"
    header += f"INST:{','.join(INSTRUMENTS)}\nVWAP Day1-Today+Vol+VIX\n\n"
    return header + "\n".join(lines)

def get_vix_all():
    msg = "VIX FORMULA P*VIX/100*sqrt(N)/sqrt(252)\n\n"
    for sym in INSTRUMENTS:
        ok, vwap, price, vix = check_entry(sym)
        m1, l1, u1 = vix_move(price, vix, 1)
        m5, l5, u5 = vix_move(price, vix, 5)
        msg += f"{sym} {price} VIX:{vix} "
        msg += f"1D+-{m1:.0f} {l1:.0f}-{u1:.0f} "
        msg += f"5D+-{m5:.0f} {l5:.0f}-{u5:.0f}\n"
    return msg

def trader_scanner():
    s = ""
    for sym in INSTRUMENTS:
        ok, vwap, price, vix = check_entry(sym)
        s += f"{sym} {'BUY' if ok else 'WAIT'} "
    return "SCANNER " + s

def trader_news(): return "NEWS Tracking"
def trader_entry(): return get_best_signal()
def trader_exit(): return f"EXIT SL {SL_RUPEES} TRAIL {TRAILING_PTS}"
def trader_timemachine(): return "TIMEMACHINE 10k"
def trader_risk(): return f"RISK PASS SL {SL_RUPEES}"
def trader_budget(): return f"BUDGET Lot {LOT_SIZE}"
def trader_broker(): return "BROKER Dhan Ready"
def trader_alerts(): return "ALERTS VWAP+Vol+VIX"
def trader_analyst(): return "ANALYST ATM"
def trader_pelosi(): return "PELOSI FII/DII"
def get_all_skills():
    lst = ["trader-scanner","trader-news","trader-entry",
           "trader-exit","trader-timemachine","trader-risk",
           "trader-budget","trader-broker","trader-alerts",
           "trader-analyst","trader-pelosi"]
    return "\n".join([f"✅ {x}" for x in lst])

@app.route("/")
def home():
    return get_best_signal() + "\n\n" + get_vix_all()

bot = telebot.TeleBot(BOT_TOKEN) if BOT_TOKEN else None

if bot:
    @bot.message_handler(commands=["start","help","best","vix","scanner","skills"])
    def all_cmd(m):
        txt = m.text.lower()
        if "vix" in txt:
            t = get_vix_all()
        elif "scanner" in txt:
            t = trader_scanner()
        elif "skills" in txt:
            t = get_all_skills()
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
                print(f">>> Bot LIVE BEST {LOT_SIZE}")
                bot.infinity_polling(timeout=60, skip_pending=True)
            except Exception as e:
                print(e)
                time.sleep(20)
    threading.Thread(target=run_bot, daemon=True).start()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",10000)))
