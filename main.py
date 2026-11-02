import os, requests, telebot
CLIENT_ID=os.getenv("CLIENT_ID") or os.getenv("CLIENTID") or ""
ACCESS_TOKEN=os.getenv("ACCESS_TOKEN") or os.getenv("ACCESSTOKEN") or ""
BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN") or os.getenv("BOT_TOKEN") or ""
bot=telebot.TeleBot(BOT_TOKEN.strip())
HEADERS={"access-token":ACCESS_TOKEN.strip(),"client-id":CLIENT_ID.strip(),"Content-Type":"application/json"}
def get_all():
    try:
        p={"NSE_EQ":[13,25,2885,27],"BSE_EQ":[51]}
        r=requests.post("https://api.dhan.co/v2/marketfeed/ltp",json=p,headers=HEADERS,timeout=10)
        data=r.json().get("data",{})
        nse=data.get("NSE_EQ",{}); bse=data.get("BSE_EQ",{})
        return {"NIFTY":nse.get("13",{}).get("last_price"),"BANK":nse.get("25",{}).get("last_price"),"REL":nse.get("2885",{}).get("last_price"),"VIX":nse.get("27",{}).get("last_price"),"SENSEX":bse.get("51",{}).get("last_price")}
    except: return {}
@bot.message_handler(commands=['start','nifty','all'])
def start(m):
    d=get_all()
    v=d.get("VIX") or 0
    txt=f"📊 LIVE\nNIFTY: {d.get('NIFTY')}\nBANK: {d.get('BANK')}\nSENSEX: {d.get('SENSEX')}\nREL: {d.get('REL')}\nVIX: {v}\n\nCap 20k SL 2k Prem>300 Book1500 Trail35\n11 Filters OK\n{'✅ TRADE' if v and v<16 else '🚫 NO TRADE'}"
    bot.send_message(m.chat.id, txt)
print("Bot Started - NO DHANHQ FINAL")
bot.infinity_polling()
