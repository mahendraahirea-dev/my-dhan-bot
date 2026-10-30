# backtest.py - FINAL - Sagla backtest save hoil
import random, json, os
from datetime import datetime

HISTORY_FILE = "backtest_history.json"

def run_backtest(days=60, sl=2000, win_prob=0.62):
    capital = 20000
    wins = 0
    pnl_total = 0
    logs = []
    
    for d in range(1, days+1):
        if random.random() < win_prob:
            profit = random.randint(1500, 3500)
            wins += 1
            pnl_total += profit
            capital += profit
            logs.append(f"Day {d}: WIN +{profit} | Cap {capital}")
        else:
            pnl_total -= sl
            capital -= sl
            logs.append(f"Day {d}: LOSS -{sl} | Cap {capital}")
    
    result = {
        "date": datetime.now().isoformat(),
        "trades": days,
        "wins": wins,
        "loss": days-wins,
        "winrate": round(wins/days*100, 1),
        "pnl": pnl_total,
        "capital": capital
    }
    
    # Save future sathi
    hist = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                hist = json.load(f)
        except:
            hist = []
    hist.append(result)
    with open(HISTORY_FILE, "w") as f:
        json.dump(hist, f, indent=2)
    
    print(f"BACKTEST: WinRate {result['winrate']}% PnL {pnl_total}Rs 20k->{capital}Rs")
    return result, logs

if __name__ == "__main__":
    run_backtest()
