#!/usr/bin/env python3
import json, time, requests
import pandas as pd

SERVER_URL = "http://172.31.35.179:8000"  # MT5 server

# ----------------------------
# Load strategy
# ----------------------------
with open("strategy.json") as f:
    strategy = json.load(f)

symbol = strategy.get("symbol")
lot = strategy.get("lot", 0.01)   
sl_pct = strategy.get("sl_pct", 0.005)   # 0.5% default
tp_pct = strategy.get("tp_pct", 0.01)    # 1% default

if not symbol:
    print("❌ No symbol found in strategy.json. Add 'symbol': 'XAUUSD' etc.")
    exit(1)

print(f"📌 Loaded strategy for {symbol}:")
print(strategy)

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
# Live trading loop
# ----------------------------
while True:
    try:
        url = f"{SERVER_URL}/candles?symbol={symbol}&timeframe=M1&count=200"
        resp = requests.get(url, timeout=10)
        if resp.status_code != 200:
            print(f"⚠️ API error {resp.status_code}: {resp.text}")
            time.sleep(30)
            continue

        candles = resp.json().get("candles", [])
        if not candles:
            print("⚠️ No candles returned, retrying...")
            time.sleep(30)
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
            else:  # SELL
                sl = entry_price * (1 + sl_pct)
                tp = entry_price * (1 - tp_pct)

            print(f"✅ {signal} at {last['time']} | Price={entry_price:.2f} | SL={sl:.2f} | TP={tp:.2f}")

            # ---- Send trade to MT5 server ----
            trade_url = f"{SERVER_URL}/trade"
            payload = {
                "symbol": symbol,
                "action": signal,
                "lot": lot,
                "sl": sl,
                "tp": tp
            }
            trade_resp = requests.post(trade_url, json=payload, timeout=10)

            if trade_resp.status_code == 200:
                print("📤 Trade request sent:", trade_resp.json())
            else:
                print(f"⚠️ Trade API error {trade_resp.status_code}: {trade_resp.text}")

        else:
            print(f"ℹ️ No signal at {last['time']} | Price={last['close']}")

    except Exception as e:
        print(f"❌ Error: {e}")

    time.sleep(60)  # wait for next candle