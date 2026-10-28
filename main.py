from fastapi import FastAPI
from datetime import datetime
import math
from zoneinfo import ZoneInfo

app = FastAPI()

def calc_expected_move(nifty_price, vix, days=1):
    return round(nifty_price * (vix/100) * math.sqrt(days/252))

@app.get("/")
def home():
    ist = ZoneInfo("Asia/Kolkata")
    now = datetime.now(ist)
    nifty = 25000
    vix = 15
    m1 = calc_expected_move(nifty, vix, 1)
    m5 = calc_expected_move(nifty, vix, 5)
    return {
        "status": "LIVE 🟢 - Deploy Fixed",
        "time": str(now),
        "formula": "Nifty * VIX/100 * sqrt(N/252)",
        "1D_move": f"±{m1}",
        "1D_Range": f"{nifty-m1} to {nifty+m1}",
        "1W_move": f"±{m5}",
        "note": "VIX shows Size Not Direction - Added!"
    }
