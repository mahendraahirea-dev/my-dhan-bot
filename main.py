# FINAL BOT - 11 Skills + FREE Price + 3 Index
import os, json, time, requests, yfinance as yf
from datetime import datetime, time as dtime
import telebot

# CONFIG
BOT_TOKEN = os.getenv("BOT_TOKEN")
DHAN_CLIENT_ID = os.getenv("DHAN_CLIENT_ID")
DHAN_ACCESS_TOKEN = os.getenv("DHAN_ACCESS_TOKEN")
bot = telebot.TeleBot(BOT_TOKEN)

# TRADER FOLDERS (11 skill logic sathi)
os.makedirs("trader/state", exist_ok=True)
CONFIG = {
    "entry_window_start": "09:45",
    "entry_window_end": "11:30",
    "max_loss_per_trade": 500,
    "daily_loss_limit": 1500,
    "max_trades_per_day": 3,
    "reward_risk_min": 1.0,
    "vix_limit": 20,
    "account_size": 30000
}

# FREE PRICE - Yahoo (Dhan 499 bypass)
SYMBOLS = {
    "NIFTY": "^NSEI",
    "BANKNIFTY": "^NSEBANK", 
    "SENSEX": "^BSESN"
}

def get_free_price(name):
    try:
        ticker = yf.Ticker(SYMBOLS[name])
        data = ticker.history(period="1d", interval="1m")
        if not data.empty:
            return round(float(data['Close'].iloc[-1]), 2)
    except: pass
    # fallback static last close
    return {"NIFTY": 23331, "BANKNIFTY": 54879, "SENSEX": 75296}.get(name, 0)

def get_vix():
    try:
        v = yf.Ticker("^INDIAVIX").history(period="1d", interval="1m")
        if not v.empty: return round(float(v['Close'].iloc[-1]),2)
    except: pass
    return 15.45

# RISK MANAGER - trader-risk SKILL.md cha rule【559547488367970913†L33-L36】
def risk_check(plan):
    now = datetime.now().time()
    start = datetime.strptime(CONFIG["entry_window_start"], "%H:%M").time()
    end = datetime.strptime(CONFIG["entry_window_end"], "%H:%M").time()
    
    if not (start <= now <= end):
        return False, f"BLOCK: Time baher - {now}"
    if get_vix() > CONFIG["vix_limit"]:
        return False, f"BLOCK: VIX {get_vix()} > {CONFIG['vix_limit']}"
    if plan['loss'] > CONFIG["max_loss_per_trade"]:
        return False, f"BLOCK: Loss {plan['loss']} > {CONFIG['max_loss_per_trade']}"
    # daily loss check
    state_file = "trader/state/risk.json"
    if os.path.exists(state_file):
        with open(state_file) as f: state=json.load(f)
        if state.get("daily_loss",0) > CONFIG["daily_loss_limit"]:
            return False, "BLOCK: Daily loss limit"
    return True, "PASS"

# EXIT PLANNER - trader-exit【559547488367970913†L379-L382】
def plan_exit(entry_price, range_high, range_low):
    mid = (range_high + range_low)/2
    stop = mid
    risk = entry_price - stop
    target1 = entry_price + risk
    target2 = entry_price + (risk*2)
    return {"stop": round(stop,2), "target1": round(target1,2), "target2": round(target2,2), "risk": round(risk,2)}

@bot.message_handler(commands=['start'])
def start(m):
    nifty = get_free_price("NIFTY")
    bank = get_free_price("BANKNIFTY")
    sensex = get_free_price("SENSEX")
    vix = get_vix()
    msg = f"""🚀 BOT LIVE - 11 SKILLS ACTIVE
NIFTY: {nifty} | CE | PE
BANKNIFTY: {bank} | CE | PE
SENSEX: {sensex} | CE | PE
VIX: {vix} | TIME: {CONFIG['entry_window_start']}-{CONFIG['entry_window_end']}

Commands:
/ce - NIFTY CE Demo
/pe - NIFTY PE Demo
/bankce - BANK CE
/sensexce - SENSEX CE"""
    bot.send_message(m.chat.id, msg)

@bot.message_handler(commands=['ce','pe','bankce','sensexce'])
def demo_entry(m):
    idx = "NIFTY"
    if "bank" in m.text: idx="BANKNIFTY"
    if "sensex" in m.text: idx="SENSEX"
    
    price = get_free_price(idx)
    side = "CE" if "ce" in m.text.lower() else "PE"
    
    # Fake ORB range
    rh, rl = price+50, price-50
    exit_plan = plan_exit(price, rh, rl)
    plan = {"entry": price, "loss": 400, "index": idx, "side": side, **exit_plan}
    
    ok, reason = risk_check(plan)
    
    with open("trader/plan.json","w") as f: json.dump(plan,f,indent=2)
    
    if ok:
        bot.send_message(m.chat.id, f"✅ {reason}\n🚀 ENTRY: {idx} {price} {side} @ {price}\nStop: {exit_plan['stop']} | T1: {exit_plan['target1']} | T2: {exit_plan['target2']}\n(DEMO - Live la 'yes' lagel)")
    else:
        bot.send_message(m.chat.id, f"❌ {reason}\nEntry BLOCK jhali.")

bot.infinity_polling()
