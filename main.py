# DHAN V2.3 SIMPLE - FINNIFTY OUT, 8 STOCKS IN
import os, time
from datetime import datetime, time as dtime
import pytz
import telebot
import yfinance as yf
from flask import Flask
import threading

IST = pytz.timezone('Asia/Kolkata')
BOT_TOKEN = os.getenv("BOT_TOKEN")
CHAT_IDS = [int(x) for x in os.getenv("CHAT_IDS","").split(",") if x]
bot = telebot.TeleBot(BOT_TOKEN)
app = Flask(__name__)

@app.route('/')
def home(): return "DHAN V2.3 RUNNING"
@app.route('/health')
def health(): return {"status":"ok"}

INDICES = ["NIFTY","BANKNIFTY","SENSEX","KOTAKBANK","SUNPHARMA","BAJAJFINSV","ASIANPAINT","MARUTI","INDUSINDBK","ULTRACEMCO","ADANIPORTS"]
LOTS = {"NIFTY":65,"BANKNIFTY":30,"SENSEX":20,"KOTAKBANK":800,"SUNPHARMA":700,"BAJAJFINSV":1000,"ASIANPAINT":400,"MARUTI":50,"INDUSINDBK":1100,"ULTRACEMCO":100,"ADANIPORTS":800}
STATE = {"date":"","done":False}

def get_price(sym):
    try:
        ticker = {"NIFTY":"^NSEI","BANKNIFTY":"^NSEBANK","SENSEX":"^BSESN"}.get(sym, sym+".NS")
        h = yf.Ticker(ticker).history(period="1d", interval="5m")
        if h.empty: return 0, 0
        close = float(h['Close'].iloc[-1])
        open_p = float(h['Open'].iloc[0])
        pct = round((close-open_p)/open_p*100, 2) if open_p else 0
        return close, pct
    except: return 0, 0

def get_atm(sym, price):
    if sym=="NIFTY": return round(price/50)*50
    if sym in ["BANKNIFTY","SENSEX"]: return round(price/100)*100
    return round(price/10)*10

def scan_best():
    best=None; best_conf=-1; best_data={}
    for sym in INDICES:
        price, pct = get_price(sym)
        if price==0: continue
        conf=50
        if abs(pct)>=0.3: conf+=20
        if abs(pct)>=0.6: conf+=10
        if abs(pct)<0.15: conf-=20
        conf=max(0,min(100,conf))
        typ="PE" if pct<0 else "CE"
        if conf>best_conf:
            best_conf=conf; best=sym
            best_data={"price":price,"pct":pct,"type":typ,"atm":get_atm(sym,price)}
    return best, best_conf, best_data

def do_auto():
    while True:
        try:
            now=datetime.now(IST)
            today=now.strftime('%d-%m-%Y')
            if now.time()>=dtime(9,15) and now.time()<=dtime(9,16):
                if STATE["date"]!=today:
                    best, conf, data = scan_best()
                    if conf>=80:
                        msg=f"🚀 AUTO 9:15\n\n{best} {data['atm']} {data['type']}\nPrice: {data['price']} ({data['pct']}%)\nLot: {LOTS.get(best,0)}\nConf: {conf}%\n\nSL: 40% khali\n1 Trade / Day"
                    else:
                        msg=f"❌ NO TRADE AAJ\nBest: {best} Conf {conf}% <80%\nLoss Protection"
                    STATE.update({"date":today,"done":True})
                    for cid in CHAT_IDS:
                        try: bot.send_message(cid,msg)
                        except: pass
                    time.sleep(70)
            time.sleep(20)
        except Exception as e:
            print(e); time.sleep(20)

@bot.message_handler(commands=['start','status','help'])
def h_block(m):
    bot.send_message(m.chat.id,"⚠️ /status BAND ahe.\nRoj 9:15 la AUTO yeil.\nTu kahi taku nako.")

@bot.message_handler(commands=['reset'])
def h_reset(m):
    global STATE
    STATE={"date":"","done":False}
    bot.send_message(m.chat.id,"✅ Reset Zala. Udya 9:15 la parat Auto yeil.")

def run_bot():
    bot.remove_webhook(); time.sleep(2)
    bot.infinity_polling(skip_pending=True)

if __name__=="__main__":
    threading.Thread(target=do_auto,daemon=True).start()
    threading.Thread(target=run_bot,daemon=True).start()
    app.run(host="0.0.0.0",port=int(os.getenv("PORT",10000)))
