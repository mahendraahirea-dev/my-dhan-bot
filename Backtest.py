# backtest.py - FUTURE PROOF - Sagle backtest save hotil
import random, json, os
from datetime import datetime

HISTORY_FILE = "backtest_history.json"

def run_backtest(days=60, lot_size=65, sl=2000, trail_min=1500, trail_max=3500, win_prob=0.62):
    capital = 20000
    wins = 0
    pnl_total = 0
    trades_log = []
    
    for day in range(1, days+1):
        is_win = random.random() < win_prob
        date_str = datetime.now().strftime("%Y-%m-%d")
        if is_win:
            profit = random.randint(trail_min, trail_max)
            wins += 1
            pnl_total += profit
            capital += profit
            trades_log.append({"day": day, "result": "WIN", "pnl": profit, "capital": capital, "date": date_str})
        else:
            pnl_total -= sl
            capital -= sl
            trades_log.append({"day": day, "result": "LOSS", "pnl": -sl, "capital": capital, "date": date_str})

    result = {
        "timestamp": datetime.now().isoformat(),
        "params": {"days": days, "lot": lot_size, "sl": sl, "win_prob": win_prob},
        "summary": {
            "trades": days,
            "wins": wins,
            "loss": days-wins,
            "winrate": round(wins/days*100, 1),
            "pnl": pnl_total,
            "start_capital": 20000,
            "end_capital": capital
        },
        "trades_log": trades_log
    }
    
    # Save history
    history = []
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE, "r") as f:
                history = json.load(f)
        except: history = []
    history.append(result)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)
    
    # Print
    print(f"=== TUJHA BOT BACKTEST {days} DAYS ===")
    print(f"Trades:{days} Win:{wins} Loss:{days-wins} WinRate:{result['summary']['winrate']}%")
    print(f"PnL:{pnl_total}Rs  20k -> {capital}Rs")
    print(f"Saved to {HISTORY_FILE} - Total backtests saved: {len(history)}")
    return result

if __name__ == "__main__":
    run_backtest()
