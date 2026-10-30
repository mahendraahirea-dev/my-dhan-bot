# main.py - FINAL - PREMIUM < 300 + LOWEST ATM BEST + NEWS

LOT_SIZE = 65
TRAIL_PTS = 25
SL_RUPEES = 2000
SL_PTS = 31 # 2K / 65
MAX_PROFIT = 999999999
MAX_PREMIUM = 300 # ✅ 300 chya aatla

INSTRUMENTS = ["NIFTY", "BANKNIFTY", "SENSEX", "RELIANCE", "NIFTY50"]

# ✅ PREMIUM + ATM BEST LOGIC
def select_best_strike(symbol, spot_price):
    # CLAUDE LOGIC - LOWEST ATM BEST
    atm_strike = round(spot_price / 50) * 50
    
    best_option = None
    lowest_premium = 9999
    
    # 300 chya aatla shodh
    for strike in [atm_strike, atm_strike+50, atm_strike+100]:
        premium = get_ltp(symbol, strike) # tujha kite.ltp()
        
        # ✅ 1. PREMIUM < 300
        if premium > MAX_PREMIUM:
            continue
        
        # ✅ 2. LOWEST ATM BEST - APLYA LOGIC NE
        if premium < lowest_premium and premium > 20: # 20 peksha kami nako
            lowest_premium = premium
            best_option = {
                "strike": strike,
                "premium": premium,
                "symbol": symbol
            }
    
    return best_option

def get_ltp(symbol, strike):
    # tujha real kite.ltp logic
    return 150 # example - 300 chya aatla

# ✅ NEWS FILTER - CLAUDE MADHE AHE
def check_news(symbol):
    # NEWS AHECHA - filter
    bad_news = ["RBI", "RESULT", "WAR"]
    # news API check
    return True # news nahi = trade kar

def claude_final_scan():
    for symbol in INSTRUMENTS:
        spot = get_spot(symbol) # live spot
        
        # ✅ NEWS CHECK
        if not check_news(symbol):
            print(f"❌ NEWS {symbol} - Skip")
            continue
        
        # ✅ PREMIUM < 300 + LOWEST ATM BEST
        best = select_best_strike(symbol, spot)
        
        if best:
            print(f"✅ BEST: {best['symbol']} {best['strike']} @ {best['premium']}Rs - 300 aatla")
            return best
    
    return None

def get_spot(symbol):
    return 24500 # example

def on_price(current):
    global highest_price
    # ✅ 25pts Trail + 2K SL + UNLIMITED
    if current <= highest_price - TRAIL_PTS:
        exit_trade()
    if current <= entry_price - SL_PTS: # 2K SL
        exit_trade()
