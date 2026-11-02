import os
import requests
import telebot

CLIENT_ID = os.getenv("CLIENT_ID") or os.getenv("CLIENTID") or ""
ACCESS_TOKEN = os.getenv("ACCESS_TOKEN") or os.getenv("ACCESSTOKEN") or ""
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or os.getenv("TELEGRAM_TOKEN") or ""

print(f"[ENV] CLIENT={CLIENT_ID} TOKEN_LEN={len(ACCESS_TOKEN.strip())}")
bot = telebot.TeleBot(BOT_TOKEN.strip())

HEADERS = {
    "access-token": ACCESS_TOKEN.strip(),
    "client-id": CLIENT_ID.strip(),
    "Content-Type": "application/json"
}

def get_all_ltp():
    try:
        payload = {"NSE_EQ": [13, 25, 2885, 27], "BSE_EQ": [51]}
        r = requests.post("https://api.dhan.co/v2/marketfeed/ltp", json=payload, headers=HEADERS, timeout=10)
        data = r.json().get("data", {})
        nse = data.get("NSE_EQ", {}); bse = data.get("BSE_EQ", {})
        return {
            "NIFTY": nse.get("13", {}).get("last_price"),
            "BANKNIFTY": nse.get("25", {}).get("last_price"),
            "RELIANCE": nse.get("2885", {}).get("last_price"),
            "VIX": nse.get("27", {}).get("last_price"),
            "SENSEX": bse.get("51", {}).get("last_price") or nse.get("51", {}).get("last_price")
        }
    except Exception as e:
        print(f"[ERR] {e}")
        return {}

@bot.message_handler(commands=['start','nifty','all'])
def start(m):
    d = get_all_ltp()
    if not d.get("NIFTY"):
        bot.send_message(m.chat.id, f"Spot Fail {d}")
        return

    CAPITAL=20000; SL=2000; TRAIL=35
    vix = d.get("VIX") or 0

    msg = f"""📊 LIVE - 5 INSTRUMENT

NIFTY: {d.get('NIFTY')}
BANKNIFTY: {d.get('BANKNIFTY')}
SENSEX: {d.get('SENSEX')}
RELIANCE: {d.get('RELIANCE')}
VIX: {d.get('VIX')}

💰 Cap {CAPITAL} | SL {SL} | Trail {TRAIL}

🧠 CLAUDE 11 FILTERS + Tujhe Rules:
1. Cap 20k / SL 2k - 10% Risk
2. Premium 300 khali NO TRADE
3. High Gamma 9:45-11:30 ONLY
4. VIX {vix} - {'SAFE' if vix and vix<16 else 'RISKY >18 NO TRADE'}
5. Nifty Trend + 20EMA
6. Bank Confirm
7. Sensex Align
8. Reliance Lead >1400
9. Entry >300 Premium / Book 1500
10. 35pts Trail - Cost + Trail
11. 11:30 Nantar No Trade

{'✅ TRADE ALLOWED' if vix and vix<16 else '🚫 NO TRADE - VIX HIGH / WAIT'}
"""
    bot.send_message(m.chat.id, msg)

print("Bot Started - FINAL NO DHANHQ - Requests Only")
bot.infinity_polling()
