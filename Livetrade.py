#!/usr/bin/env python3
import json, time, requests, sys
import pandas as pd
from datetime import datetime, timedelta

SERVER_URL = "http://ec2-44-242-196-239.us-west-2.compute.amazonaws.com:8000"

# ----------------------------
# CLI flag for auto-closing trades
# ----------------------------
AUTO_CLOSE = True
if len(sys.argv) > 1 and sys.argv[1].lower() in ("false", "0", "no"):
    AUTO_CLOSE = False
print(f"⚙️ Auto-close trades enabled: {AUTO_CLOSE}")

# ----------------------------
# Global state
# ----------------------------
flagged_trades = {}  # {ticket: {"open_time": datetime}}
last_candle_time = None
trade_summary = {
    "initial_balance": 1000,
    "total_trades": 0,
    "wins": 0,
    "losses": 0,
    "balance": 1000
}

# ----------------------------
# Save trade summary
# ----------------------------
def save_summary():
    with open("summary.json", "w") as f:
        json.dump(trade_summary, f, indent=2)

# ----------------------------
# Reload strategy
# ----------------------------
def load_strategy():
    try:
        with open("LIVE.json") as f:
            strategy = json.load(f)
        return strategy
    except Exception as e:
        print(f"⚠️ Error loading strategy.json: {e}")
        return {}

# ----------------------------
# RSI calculation
# ----------------------------
def calc_rsi(series, period=14):
    delta = series.diff()
    gain = delta.where(delta > 0, 0.0)
    loss = -delta.where(delta < 0, 0.0)
    avg_gain = gain.rolling(window=period).mean()
    avg_loss = loss.rolling(window=period).mean()
    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))

# ----------------------------
# Helper functions
# ----------------------------
def check_positions():
    try:
        resp = requests.get(f"{SERVER_URL}/positions", timeout=10)
        if resp.status_code == 200:
            return resp.json().get("positions", [])
    except Exception as e:
        print(f"⚠️ Error fetching positions: {e}")
    return []

def close_trade(ticket):
    try:
        resp = requests.post(f"{SERVER_URL}/close_trade", json={"ticket": ticket}, timeout=10)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

# ----------------------------
# Main Loop
# ----------------------------
pos_check_counter = 0

while True:
    try:
        # --- Reload strategy each second ---
        strategy = load_strategy()
        symbol = strategy.get("symbol")
        if not symbol:
            print("❌ No symbol in strategy.json")
            time.sleep(1)
            continue

        # Auto lot sizing
        if any(x in symbol.upper() for x in ["BTC", "ETH", "XAU"]):
            lot = 0.01
        else:
            lot = 0.1

        sl_pct = strategy.get("sl_pct", 0.005)
        tp_pct = strategy.get("tp_pct", 0.01)
        can_trade = strategy.get("winrate", 0) >= 50

        print(f"📌 Strategy reloaded | Symbol={symbol} | lot={lot} | can_trade={can_trade}")

        # --- Fetch candles ---
        resp = requests.get(f"{SERVER_URL}/candles?symbol={symbol}&timeframe=M1&count=200", timeout=10)
        candles = resp.json().get("candles", [])
        if not candles:
            print("⚠️ No candles returned")
            time.sleep(1)
            continue

        df = pd.DataFrame(candles)
        df["time"] = pd.to_datetime(df["time"])
        df["RSI"] = calc_rsi(df["close"], strategy["rsi_period"])
        df["EMA_fast"] = df["close"].ewm(span=strategy["ema_fast"], adjust=False).mean()
        df["EMA_slow"] = df["close"].ewm(span=strategy["ema_slow"], adjust=False).mean()

        last = df.iloc[-1]

        print(f"🕒 Candle {last['time']} | O={last['open']} H={last['high']} L={last['low']} C={last['close']}")

        # --- Prevent duplicate trades in same candle ---
        if last_candle_time == last["time"]:
            print("⏸ Already processed this candle, skipping...")
        else:
            last_candle_time = last["time"]

            # --- Generate signal ---
            signal = None
            if last["EMA_fast"] > last["EMA_slow"] and last["RSI"] < strategy["rsi_buy"]:
                signal = "BUY"
            elif last["EMA_fast"] < last["EMA_slow"] and last["RSI"] > strategy["rsi_sell"]:
                signal = "SELL"

            if signal:
                if not can_trade:
                    print("🚫 Strategy winrate < 50, skipping trade")
                else:
                    entry_price = last["close"]
                    if signal == "BUY":
                        sl = entry_price * (1 - sl_pct)
                        tp = entry_price * (1 + tp_pct)
                    else:
                        sl = entry_price * (1 + sl_pct)
                        tp = entry_price * (1 - tp_pct)

                    print(f"✅ Signal {signal} | Entry={entry_price:.2f} | SL={sl:.2f} | TP={tp:.2f}")

                    payload = {"symbol": symbol, "action": signal, "lot": lot, "sl": sl, "tp": tp}
                    trade_resp = requests.post(f"{SERVER_URL}/trade", json=payload, timeout=10).json()
                    print("📤 Trade request:", trade_resp)

                    if trade_resp.get("status") == "success":
                        ticket = trade_resp["details"].get("order") or trade_resp["details"].get("position")
                        if ticket:
                            flagged_trades[ticket] = {"open_time": datetime.utcnow()}
                            trade_summary["total_trades"] += 1
                            save_summary()
                            print(f"🎯 Tracking trade ticket {ticket}")
            else:
                print("ℹ️ No signal matched")

        # --- Manage flagged trades every 5 sec ---
        if pos_check_counter % 5 == 0:
            positions = check_positions()
            now = datetime.utcnow()

            for pos in positions:
                ticket = pos["ticket"]
                profit = pos["profit"]

                if ticket in flagged_trades:
                    opened = flagged_trades[ticket]["open_time"]
                    if now - opened > timedelta(minutes=5):
                        if AUTO_CLOSE:
                            if profit > 0:
                                print(f"💰 Closing trade {ticket} with profit={profit}")
                                result = close_trade(ticket)
                                print("CLOSE RESULT:", result)
                                flagged_trades.pop(ticket, None)
                            else:
                                print(f"⚠️ Trade {ticket} still in loss after 5min, waiting...")

        pos_check_counter += 1

    except Exception as e:
        print(f"❌ Error: {e}")

    time.sleep(1)