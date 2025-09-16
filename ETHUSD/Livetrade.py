#!/usr/bin/env python3
import json, time, requests
import pandas as pd
from datetime import datetime, timedelta

SERVER_URL = "http://ec2-44-242-196-239.us-west-2.compute.amazonaws.com:8000"

# ----------------------------
# Load strategy each minute
# ----------------------------
def load_strategy():
    try:
        with open("LIVE.json") as f:
            return json.load(f)
    except Exception as e:
        print(f"⚠️ Could not load LIVE.json: {e}")
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

def get_balance():
    try:
        resp = requests.get(f"{SERVER_URL}/balance", timeout=10)
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        print(f"⚠️ Error fetching balance: {e}")
    return None

# ----------------------------
# Trade tracker
# ----------------------------
flagged_trades = {}  # {ticket: {"open_time": datetime}}
initial_balance = get_balance()
if initial_balance:
    print(f"💰 Initial Balance = {initial_balance['balance']} {initial_balance['currency']}")

# ----------------------------
# Live trading loop
# ----------------------------
last_strategy_reload = None
strategy = {}

while True:
    try:
        # reload strategy every minute
        if not last_strategy_reload or (datetime.utcnow() - last_strategy_reload).seconds >= 60:
            strategy = load_strategy()
            last_strategy_reload = datetime.utcnow()
            winrate = strategy.get("winrate", 0)
            wins = strategy.get("wins", 0)
            balance = get_balance()
            equity_guard = False

            # equity guard check
            if balance:
                floating_dd = balance["balance"] - balance["equity"]
                if floating_dd > 50:  # 🔒 pause if drawdown > $50
                    equity_guard = True

            can_trade = winrate > 50 and wins >= 7 and balance and balance["balance"] > 1400 and not equity_guard
            print(f"🔄 Strategy reloaded. can_trade={can_trade} | winrate={winrate:.2f}% | wins={wins} | balance={balance['balance'] if balance else 'N/A'} | equity_guard={equity_guard}")

        # skip new trades if cannot trade
        if not strategy or not can_trade:
            # still check open flagged trades
            now = datetime.utcnow()
            positions = check_positions()
            for pos in positions:
                ticket = pos["ticket"]
                profit = pos["profit"]
                if ticket in flagged_trades:
                    opened = flagged_trades[ticket]["open_time"]
                    if now - opened > timedelta(minutes=5):
                        if profit > 0:
                            print(f"💰 Closing trade {ticket} with profit={profit}")
                            result = close_trade(ticket)
                            print("CLOSE RESULT:", result)
                            flagged_trades.pop(ticket, None)
                        else:
                            print(f"⚠️ Trade {ticket} still in loss after 5min, waiting for profit...")
            time.sleep(1)
            continue

        # ----------------------------
        # Get candles
        # ----------------------------
        symbol = strategy.get("symbol")
        sl_pct = strategy.get("sl_pct", 0.005)
        tp_pct = strategy.get("tp_pct", 0.01)
        lot = 0.01 if any(x in symbol.upper() for x in ["BTC", "ETH", "XAU"]) else 0.1

        url = f"{SERVER_URL}/candles?symbol={symbol}&timeframe=M1&count=200"
        resp = requests.get(url, timeout=10)
        candles = resp.json().get("candles", [])
        if not candles:
            time.sleep(1)
            continue

        df = pd.DataFrame(candles)
        df["time"] = pd.to_datetime(df["time"])
        df["RSI"] = calc_rsi(df["close"], strategy["rsi_period"])
        df["EMA_fast"] = df["close"].ewm(span=strategy["ema_fast"], adjust=False).mean()
        df["EMA_slow"] = df["close"].ewm(span=strategy["ema_slow"], adjust=False).mean()

        last = df.iloc[-1]
        signal = None
        if last["EMA_fast"] > last["EMA_slow"] and last["RSI"] < strategy["rsi_buy"]:
            signal = "BUY"
        elif last["EMA_fast"] < last["EMA_slow"] and last["RSI"] > strategy["rsi_sell"]:
            signal = "SELL"

        if signal:
            entry_price = last["close"]
            if signal == "BUY":
                sl = entry_price * (1 - sl_pct)
                tp = entry_price * (1 + tp_pct)
            else:
                sl = entry_price * (1 + sl_pct)
                tp = entry_price * (1 - tp_pct)

            print(f"✅ {signal} at {last['time']} | Price={entry_price:.2f} | SL={sl:.2f} | TP={tp:.2f}")

            payload = {"symbol": symbol, "action": signal, "lot": lot, "sl": sl, "tp": tp}
            trade_resp = requests.post(f"{SERVER_URL}/trade", json=payload, timeout=10).json()
            print("📤 Trade request sent:", trade_resp)

            if trade_resp.get("status") == "success":
                ticket = trade_resp["details"].get("order") or trade_resp["details"].get("position")
                if ticket:
                    flagged_trades[ticket] = {"open_time": datetime.utcnow()}
                    print(f"🎯 Tracking trade ticket {ticket}")

        else:
            print(f"ℹ️ No signal at {last['time']} | Price={last['close']}")

        # ----------------------------
        # Manage flagged trades
        # ----------------------------
        now = datetime.utcnow()
        positions = check_positions()
        for pos in positions:
            ticket = pos["ticket"]
            profit = pos["profit"]
            if ticket in flagged_trades:
                opened = flagged_trades[ticket]["open_time"]
                if now - opened > timedelta(minutes=5):
                    if profit > 0:
                        print(f"💰 Closing trade {ticket} with profit={profit}")
                        result = close_trade(ticket)
                        print("CLOSE RESULT:", result)
                        flagged_trades.pop(ticket, None)
                    else:
                        print(f"⚠️ Trade {ticket} still in loss after 5min, waiting for profit...")

    except Exception as e:
        print(f"❌ Error: {e}")

    time.sleep(1)  # run fast loop