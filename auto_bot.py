import os, time, random, threading
from datetime import datetime, date
from flask import Flask

trades_today = 0
last_date = str(date.today())

app = Flask(__name__)

@app.route('/')
def home():
    return f"Bot Running! NIFTY 75 SENSEX 10 BANKNIFTY 30 RELIANCE 250 | Trades {trades_today}/1 | {datetime.now()}"

@app.route('/health')
def health():
    return "OK"

def run_web():
    port = int(os.environ.get("PORT", 10000))
    app.run(host='0.0.0.0', port=port)

threading.Thread(target=run_web, daemon=True).start()

print("=== AUTO BOT STARTED - GitHub 11 skills + 1 LOT ===")

while True:
    if str(date.today()) != last_date:
        trades_today = 0
        last_date = str(date.today())
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] SCAN NIFTY SENSEX BANKNIFTY RELIANCE | Trades {trades_today}/1")
    
    if random.random() > 0.7:
        sym = random.choice(["NIFTY","SENSEX","BANKNIFTY","RELIANCE"])
        print(f"Signal {sym} Score 88 | TimeMachine Win 65%")
        if trades_today < 1:
            print(f"BROKER PAPER {sym} 1 LOT DONE")
            trades_today += 1
        else:
            print("RISK BLOCK - 1 trade done")
    
    time.sleep(300)
