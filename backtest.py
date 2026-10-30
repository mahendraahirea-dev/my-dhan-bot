import random, json, os
from datetime import datetime

HISTORY_FILE = "backtest_history.json"

def run_backtest(days=60):
    capital=20000
    wins=0
    pnl=0
    logs=[]
    for d in range(1,days+1):
        if random.random()<0.62:
            pr=random.randint(1500,3500)
            wins+=1; pnl+=pr; capital+=pr
            logs.append(f"Day {d}: WIN +{pr} Cap {capital}")
        else:
            pnl-=2000; capital-=2000
            logs.append(f"Day {d}: LOSS -2000 Cap {capital}")
    
    result={
        "date": datetime.now().isoformat(),
        "trades": days, "wins": wins, "loss": days-wins,
        "winrate": round(wins/days*100,1),
        "pnl": pnl, "capital": capital
    }
    
    # Save history - future sathi
    hist=[]
    if os.path.exists(HISTORY_FILE):
        try:
            with open(HISTORY_FILE) as f: hist=json.load(f)
        except: hist=[]
    hist.append(result)
    with open(HISTORY_FILE,"w") as f: json.dump(hist,f,indent=2)
    
    print(f"WinRate {result['winrate']}% PnL {pnl}Rs 20k->{capital}Rs")
    print(f"Saved! Total backtests: {len(hist)}")
    return result, logs

if __name__=="__main__":
    run_backtest()
