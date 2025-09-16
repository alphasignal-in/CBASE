#!/usr/bin/env python3
"""
Final Bruteforce strategy tester for MT5 JSON candlestick files.
- Supports MT5 JSON format
- Auto-adjusts SL/TP for FX vs Gold/Crypto
- Uses realistic max_lookahead for trades
- Saves best strategy with 'symbol' for live trader
"""

import json, sys, time, math, os
from datetime import datetime
import pandas as pd
import numpy as np

# -----------------------------
# RSI calculation
# -----------------------------
def calc_rsi_np(close, period=14):
    s = pd.Series(close).diff()
    gain = s.where(s > 0, 0.0).rolling(window=period, min_periods=period).mean()
    loss = (-s.where(s < 0, 0.0)).rolling(window=period, min_periods=period).mean()
    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.fillna(0).to_numpy()

# -----------------------------
# Strategy backtester
# -----------------------------
def run_strategy(data, ema_fast, ema_slow, rsi_period, rsi_buy, rsi_sell, sl_pct, tp_pct,
                 starting_balance=1000.0, risk_per_trade=20.0, max_lookahead=300):
    close = data["close"].to_numpy()
    high = data["high"].to_numpy()
    low = data["low"].to_numpy()
    openp = data["open"].to_numpy()
    n = len(close)
    if n < 2:
        return {"balance": starting_balance, "wins": 0, "losses": 0, "trades": 0, "winrate": 0.0}

    ema_fast_arr = pd.Series(close).ewm(span=ema_fast, adjust=False).mean().to_numpy()
    ema_slow_arr = pd.Series(close).ewm(span=ema_slow, adjust=False).mean().to_numpy()
    rsi_arr = calc_rsi_np(close, period=rsi_period)

    signals = np.array([""] * n, dtype=object)
    buy_mask = (ema_fast_arr > ema_slow_arr) & (rsi_arr < rsi_buy)
    sell_mask = (ema_fast_arr < ema_slow_arr) & (rsi_arr > rsi_sell)
    signals[buy_mask] = "BUY"
    signals[sell_mask] = "SELL"

    balance = float(starting_balance)
    wins = losses = trades = 0

    for i in range(n - 1):
        signal = signals[i]
        if signal == "":
            continue

        entry = openp[i + 1]
        if math.isnan(entry) or entry == 0:
            continue

        if signal == "BUY":
            sl = entry * (1 - sl_pct)
            tp = entry * (1 + tp_pct)
        else:
            sl = entry * (1 + sl_pct)
            tp = entry * (1 - tp_pct)

        j_end = n if (max_lookahead is None) else min(n, i + 1 + max_lookahead)
        highs = high[i + 1:j_end]
        lows = low[i + 1:j_end]

        if signal == "BUY":
            tp_hits = np.nonzero(highs >= tp)[0]
            sl_hits = np.nonzero(lows <= sl)[0]
        else:
            tp_hits = np.nonzero(lows <= tp)[0]
            sl_hits = np.nonzero(highs >= sl)[0]

        if tp_hits.size == 0 and sl_hits.size == 0:
            continue  # trade expired without outcome

        t_idx = tp_hits[0] if tp_hits.size > 0 else None
        s_idx = sl_hits[0] if sl_hits.size > 0 else None

        if t_idx is None:
            outcome = "LOSS"
        elif s_idx is None:
            outcome = "WIN"
        else:
            outcome = "WIN" if t_idx < s_idx else "LOSS"

        trades += 1
        if outcome == "WIN":
            wins += 1
            profit = risk_per_trade * (tp_pct / sl_pct) if sl_pct != 0 else risk_per_trade * tp_pct
            balance += profit
        else:
            losses += 1
            balance -= risk_per_trade

    winrate = (wins / trades * 100.0) if trades > 0 else 0.0
    return {"balance": balance, "wins": wins, "losses": losses, "trades": trades, "winrate": winrate}

# -----------------------------
# Load MT5 JSON data
# -----------------------------
def load_mt5_json(path):
    with open(path, "r") as f:
        payload = json.load(f)
    candles = payload.get("candles", [])
    df = pd.DataFrame(candles)
    for col in ["open", "high", "low", "close", "tick_volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["time"] = pd.to_datetime(df["time"])
    df = df[["time", "open", "high", "low", "close", "tick_volume"]].sort_values("time").reset_index(drop=True)
    return payload.get("symbol", "UNKNOWN"), payload.get("timeframe", "?"), df

# -----------------------------
# Detect asset type
# -----------------------------
def detect_asset_type(symbol):
    symbol = symbol.upper()
    if "BTC" in symbol or "ETH" in symbol or "XAU" in symbol:
        return "CRYPTO"
    return "FX"

# -----------------------------
# Main bruteforce
# -----------------------------
def main(path, max_lookahead=300):
    symbol, timeframe, df = load_mt5_json(path)
    asset_type = detect_asset_type(symbol)
    print(f"Loaded {len(df)} candles from {path} (symbol={symbol}, timeframe={timeframe}, type={asset_type})")

    # parameter ranges
    ema_fast_range = [5, 9, 12]
    ema_slow_range = [21, 30, 50]
    rsi_period_range = [7, 14]
    rsi_buy_range = [40, 45, 50]
    rsi_sell_range = [50, 55, 60]

    if asset_type == "FX":
        sl_range = [0.0005, 0.001]   # 0.05%–0.1%
        tp_range = [0.001, 0.002]    # 0.1%–0.2%
    else:
        sl_range = [0.005, 0.01]     # 0.5%–1%
        tp_range = [0.01, 0.02]      # 1%–2%

    all_combos = [(ef, es, rp, rb, rs, sl, tp) for ef in ema_fast_range for es in ema_slow_range
                  for rp in rsi_period_range for rb in rsi_buy_range for rs in rsi_sell_range
                  for sl in sl_range for tp in tp_range if ef < es]
    total = len(all_combos)
    print(f"Total parameter sets to test: {total} (SL/TP ranges auto-set for {asset_type})\n")

    best = {"balance": -1e18}
    start = time.time()
    for idx, (ef, es, rp, rb, rs, sl, tp) in enumerate(all_combos, start=1):
        res = run_strategy(df, ef, es, rp, rb, rs, sl, tp, max_lookahead=max_lookahead)
        if res["balance"] > best["balance"]:
            best = {"balance": res["balance"], "ema_fast": ef, "ema_slow": es, "rsi_period": rp,
                    "rsi_buy": rb, "rsi_sell": rs, "sl_pct": sl, "tp_pct": tp,
                    "wins": res["wins"], "losses": res["losses"],
                    "trades": res["trades"], "winrate": res["winrate"],
                    "symbol": symbol}
            print(f"[NEW BEST @ {idx}/{total}] Balance=${res['balance']:.2f}, WinRate={res['winrate']:.2f}%, Trades={res['trades']}")
        if idx % 40 == 0 or idx == total:
            elapsed = time.time() - start
            print(f"Checked {idx}/{total} combos... elapsed={elapsed:.1f}s")

    print("\n✅ Best Strategy Found:")
    print(best)

    # Save to strategy.json
    with open("strategy.json", "w") as f:
        json.dump(best, f, indent=2)
    print("Saved best strategy => strategy.json")
    return best

# -----------------------------
# CLI
# -----------------------------
if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("Usage: python bruteforce.py path/to/SYMBOL.json [max_lookahead]")
        sys.exit(1)
    path = sys.argv[1]
    if len(sys.argv) > 2 and sys.argv[2].lower() in ('none', 'null', '0'):
        max_look = None
    else:
        max_look = int(sys.argv[2]) if len(sys.argv) > 2 else 300
    main(path, max_look)