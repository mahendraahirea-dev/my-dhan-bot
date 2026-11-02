import os
import requests
import telebot

# --- ENV - donhi naav chaltil ---
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
        print(f"[DHAN] {r.text[:600]}")
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

def claude_11_filters_with_your_rules(d):
    nifty = d.get("NIFTY") or 0
    bank = d.get("BANKNIFTY") or 0
    vix = d.get("VIX") or 0
    
    # Tujhe rules
    CAPITAL = 20000
    SL_PER_TRADE = 2000
    PREMIUM_MIN = 300
    BOOK_TARGET = 1500
    TRAIL_PTS = 35
    HIGH_GAMMA_TIME = "9:45-11:30"

    txt = f"""📊 LIVE:
NIFTY: {d.get('NIFTY')} | BANK: {d.get('BANKNIFTY')}
SENSEX: {d.get('SENSEX')} | RELI: {d.get('RELIANCE')} | VIX: {d.get('VIX')}

💰 Tujha Setup: Cap {CAPITAL} | SL {SL_PER_TRADE} | Book {BOOK_TARGET}

🧠 CLAUDE 11 FILTERS + TUJHE RULES:

1.  Capital Filter: {CAPITAL} - 2k SL - Risk 10% OK
2.  Premium Filter: 300 Khali No Trade (Theta Bachav)
3.  High Gamma Filter: {HIGH_GAMMA_TIME} Madhech Trade - Gamma Blast
4.  VIX Filter: {vix} - {'SAFE ( <16 )' if vix and vix<16 else 'NO TRADE ( >18 )'}
5.  Nifty Trend: {nifty} - Above/Below 20EMA Check
6.  Bank Confirm: {bank} - Bank + Nifty Doni Green Pahije
7.  Sensex Align: Sensex Trend Follow
8.  Reliance Lead: Reliance >1400 - Market Support
9.  Entry: 300+ Premium Ghyaycha, 1500 Book Karaycha
10. Trail Rule: {TRAIL_PTS} Pts Nantar SL to Cost + Trail 35-35
11. No Trade Zone: 11:30 Nantar No High Gamma

🎯 FINAL PLAN:
- Entry Premium > {PREMIUM_MIN}
- SL = {SL_PER_TRADE} (2k)
- Target = {BOOK_TARGET} Book
- 35 Pts Ale Ki SL Cost La + Trail Chalu
- 1500 La 50% Book, Baki Trail
"""
    if vix and vix > 18:
        txt += "\n🚫 FINAL: AAJ NO TRADE - VIX JAST"
    elif vix and vix < 16 and nifty:
        txt += "\n✅ FINAL: TRADE ALLOWED - HIGH GAMMA MODE ON"
    else:
        txt += "\n⚠️ FINAL: WAIT"
    return txt

@bot.message_handler(commands=['start','nifty','all','filters'])
def start(m):
    data = get_all_ltp()
    if not data.get("NIFTY"):
        bot.send_message(m.chat.id, f"Data Fail {data}")
        return
    bot.send_message(m.chat.id, claude_11_filters_with_your_rules(data))

print("Bot Started - 20k Cap 2k SL 300 Premium High Gamma 1500 Book 35 Trail")
bot.infinity_polling()
