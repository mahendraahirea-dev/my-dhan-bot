from fastapi import FastAPI

app = FastAPI()

CONFIG = {
    "VERSION": "V34 - FINAL - 1 LOT 1 TRADE ONLY",
    "MODE": "PAPER",
    "MAX_TRADES": 1,
    "ALLOW": ["NIFTY", "BANKNIFTY_WEEKLY", "RELIANCE"],
    "BLOCK": ["HDFC", "HDFCBANK"]
}

trades = 0

@app.get("/")
def home():
    return {
        "status": CONFIG["VERSION"],
        "mode": "PAPER - NO MONEY",
        "rule": "1 LOT = 1 TRADE - HDFC BLOCKED",
        "pos": [],
        "pnl": 0,
        "trades_today": trades
    }
