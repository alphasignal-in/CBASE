#!/usr/bin/env python3
import json, time, requests
import pandas as pd
from datetime import datetime, timedelta
import sys

SERVER_URL = "http://172.31.35.179:8000"

# ----------------------------
# Config
# ----------------------------
close_bad_trades = False
if len(sys.argv) > 1 and sys.argv[1].lower() == "true":
    close_bad_trades = True

print(f"📌 Close underperforming trades enabled: {close_bad_trades}")

# ----------------------------
# Load strategy (reload every loop)
# ----------------------------
def load_strategy():
    try:
        with open("LIVE.json") as f:
            strat = json.load(f)
        return strat
    except Exception as e:
        print(f"⚠️ Failed to load LIVE.json: {e}")
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
# Helpers
# ----------------------------
flagged_trades = {}  # {ticket: {"open_time": datetime}}

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
# Live trading loop
# ----------------------------
while True:
    try:
        # --- Reload strategy ---
        strategy = load_strategy()
        if not strategy:
            print("❌ No strategy loaded, skipping this cycle.")
            time.sleep(60)
            continue

        symbol = strategy.get("symbol")
        sl_pct = strategy.get("sl_pct", 0.005)
        tp_pct = strategy.get("tp_pct", 0.01)
        winrate = strategy.get("winrate", 0)
        wins = strategy.get("wins", 0)
        balance = strategy.get("balance", 1000)

        # auto lot selection
        if any(x in symbol.upper() for x in ["BTC", "ETH", "XAU"]):
            lot = 0.01
        else:
            lot = 0.1

        print(f"📌 Strategy reloaded: {symbol}, winrate={winrate:.2f}%, wins={wins}, balance={balance}, lot={lot}")

        # --- Can trade check ---
        can_trade = True
        if winrate <= 50:
            print("⏸️ Paused: winrate <= 50%")
            can_trade = False
        if wins < 7:
            print("⏸️ Paused: wins < 7")
            can_trade = False
        if balance <= 1400:
            print("⏸️ Paused: balance <= 1400")
            can_trade = False

        # --- Fetch candles ---
        url = f"{SERVER_URL}/candles?symbol={symbol}&timeframe=M1&count=200"
        resp = requests.get(url, timeout=10)
        candles = resp.json().get("candles", [])
        if not candles:
            print("⚠️ No candles returned")
            time.sleep(60)
            continue

        df = pd.DataFrame(candles)
        df["time"] = pd.to_datetime(df["time"])
        df["RSI"] = calc_rsi(df["close"], strategy["rsi_period"])
        df["EMA_fast"] = df["close"].ewm(span=strategy["ema_fast"], adjust=False).mean()
        df["EMA_slow"] = df["close"].ewm(span=strategy["ema_slow"], adjust=False).mean()

        last = df.iloc[-1]
        print(f"🕒 New candle {last['time']} | Price={last['close']}")

        signal = None
        if last["EMA_fast"] > last["EMA_slow"] and last["RSI"] < strategy["rsi_buy"]:
            signal = "BUY"
        elif last["EMA_fast"] < last["EMA_slow"] and last["RSI"] > strategy["rsi_sell"]:
            signal = "SELL"

        if signal and can_trade:
            entry_price = last["close"]

            if signal == "BUY":
                sl = entry_price * (1 - sl_pct)
                tp = entry_price * (1 + tp_pct)
            else:
                sl = entry_price * (1 + sl_pct)
                tp = entry_price * (1 - tp_pct)

            print(f"✅ {signal} | SL={sl:.2f} | TP={tp:.2f}")

            payload = {"symbol": symbol, "action": signal, "lot": lot, "sl": sl, "tp": tp}
            trade_resp = requests.post(f"{SERVER_URL}/trade", json=payload, timeout=10).json()
            print("📤 Trade request sent:", trade_resp)

            if trade_resp.get("status") == "success":
                ticket = trade_resp["details"].get("order") or trade_resp["details"].get("position")
                if ticket:
                    flagged_trades[ticket] = {"open_time": datetime.utcnow()}
                    print(f"🎯 Tracking trade ticket {ticket}")
        else:
            print("ℹ️ No signal or trading paused.")

        # --- Manage flagged trades ---
        now = datetime.utcnow()
        positions = check_positions()

        for pos in positions:
            ticket = pos["ticket"]
            profit = pos["profit"]

            if ticket in flagged_trades:
                opened = flagged_trades[ticket]["open_time"]
                if close_bad_trades and now - opened > timedelta(minutes=5):
                    if profit > 0:
                        print(f"💰 Closing trade {ticket} with profit={profit}")
                        result = close_trade(ticket)
                        print("CLOSE RESULT:", result)
                        flagged_trades.pop(ticket, None)
                    else:
                        print(f"⚠️ Trade {ticket} still in loss after 5min, waiting for profit...")

    except Exception as e:
        print(f"❌ Error: {e}")

    time.sleep(60)  # wait 1 min