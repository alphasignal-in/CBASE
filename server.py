from fastapi import FastAPI
from pydantic import BaseModel
from datetime import datetime
from typing import Optional
import MetaTrader5 as mt5

app = FastAPI()

# ---------------------------
# Startup / Shutdown
# ---------------------------
@app.on_event("startup")
def startup_event():
    if not mt5.initialize():
        print("❌ MT5 initialization failed")
    else:
        print("✅ Connected to MT5")

@app.on_event("shutdown")
def shutdown_event():
    mt5.shutdown()

# ---------------------------
# Balance
# ---------------------------
@app.get("/balance")
def get_balance():
    account_info = mt5.account_info()
    if account_info is None:
        return {"error": "Failed to fetch account info"}
    return {
        "login": account_info.login,
        "balance": account_info.balance,
        "equity": account_info.equity,
        "currency": account_info.currency,
    }

# ---------------------------
# Symbols
# ---------------------------
@app.get("/symbols")
def get_symbols():
    symbols = mt5.symbols_get()
    if symbols is None:
        return {"error": "Failed to fetch symbols"}
    return {"symbols": [s.name for s in symbols]}

# ---------------------------
# Candles
# ---------------------------
@app.get("/candles")
def get_candles(symbol: str, timeframe: str = "M1", count: int = 600):
    tf_map = {
        "M1": mt5.TIMEFRAME_M1,
        "M5": mt5.TIMEFRAME_M5,
        "M15": mt5.TIMEFRAME_M15,
        "H1": mt5.TIMEFRAME_H1,
        "D1": mt5.TIMEFRAME_D1,
    }
    if timeframe not in tf_map:
        return {"error": "Invalid timeframe"}

    rates = mt5.copy_rates_from(symbol, tf_map[timeframe], datetime.now(), count)
    if rates is None:
        return {"error": f"Failed to fetch candles for {symbol}"}

    candles = []
    for r in rates:
        candles.append({
            "time": datetime.fromtimestamp(r['time']).strftime('%Y-%m-%d %H:%M:%S'),
            "open": float(r['open']),
            "high": float(r['high']),
            "low": float(r['low']),
            "close": float(r['close']),
            "tick_volume": int(r['tick_volume']),
        })
    return {"symbol": symbol, "timeframe": timeframe, "candles": candles}

# ---------------------------
# Trade Request Model
# ---------------------------
class TradeRequest(BaseModel):
    symbol: str
    action: str   # "BUY" or "SELL"
    lot: float
    sl: Optional[float] = None   # Stop Loss price
    tp: Optional[float] = None   # Take Profit price

# ---------------------------
# Trade
# ---------------------------
@app.post("/trade")
def place_trade(req: TradeRequest):
    symbol = req.symbol
    action = req.action.upper()
    lot = req.lot

    if not mt5.symbol_select(symbol, True):
        return {"error": f"Symbol {symbol} not available"}

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return {"error": "Failed to get price tick"}

    if action == "BUY":
        order_type = mt5.ORDER_TYPE_BUY
        price = tick.ask
    elif action == "SELL":
        order_type = mt5.ORDER_TYPE_SELL
        price = tick.bid
    else:
        return {"error": f"Invalid action {action}"}

    # Detect supported filling mode
    info = mt5.symbol_info(symbol)
    if info is None:
        return {"error": f"Could not fetch symbol info for {symbol}"}

    if info.filling_mode & mt5.ORDER_FILLING_FOK:
        filling = mt5.ORDER_FILLING_FOK
    elif info.filling_mode & mt5.ORDER_FILLING_IOC:
        filling = mt5.ORDER_FILLING_IOC
    else:
        filling = mt5.ORDER_FILLING_RETURN

    print(f"ℹ️ Using filling mode {filling} for {symbol}")

    request = {
        "action": mt5.TRADE_ACTION_DEAL,
        "symbol": symbol,
        "volume": lot,
        "type": order_type,
        "price": price,
        "deviation": 20,
        "magic": 123456,
        "comment": "AlphaBot trade",
        "type_time": mt5.ORDER_TIME_GTC,
        "type_filling": filling,
    }

    if req.sl:
        request["sl"] = req.sl
    if req.tp:
        request["tp"] = req.tp

    result = mt5.order_send(request)

    if result is None:
        return {"error": "order_send() returned None", "details": mt5.last_error()}

    if result.retcode != mt5.TRADE_RETCODE_DONE:
        return {"error": "Trade failed", "details": result._asdict()}

    return {"status": "success", "details": result._asdict()}

# ---------------------------
# Symbol Info
# ---------------------------
@app.get("/symbol_info")
def symbol_info(symbol: str):
    info = mt5.symbol_info(symbol)
    if info is None:
        return {"error": f"Symbol {symbol} not found"}

    return {
        "symbol": info.name,
        "trade_mode": info.trade_mode,
        "filling_mode": info.filling_mode,
        "filling_modes_allowed": {
            "FOK": bool(info.filling_mode & mt5.ORDER_FILLING_FOK),
            "IOC": bool(info.filling_mode & mt5.ORDER_FILLING_IOC),
            "RETURN": bool(info.filling_mode & mt5.ORDER_FILLING_RETURN),
        },
        "details": info._asdict()
    }

# ---------------------------
# Close All Positions
# ---------------------------
@app.post("/close_all")
def close_all():
    positions = mt5.positions_get()
    if positions is None or len(positions) == 0:
        return {"status": "no positions open"}

    closed = []
    errors = []

    for pos in positions:
        symbol = pos.symbol
        volume = pos.volume
        if pos.type == mt5.POSITION_TYPE_BUY:
            order_type = mt5.ORDER_TYPE_SELL
            price = mt5.symbol_info_tick(symbol).bid
        else:
            order_type = mt5.ORDER_TYPE_BUY
            price = mt5.symbol_info_tick(symbol).ask

        # Detect filling mode again
        info = mt5.symbol_info(symbol)
        if info.filling_mode & mt5.ORDER_FILLING_FOK:
            filling = mt5.ORDER_FILLING_FOK
        elif info.filling_mode & mt5.ORDER_FILLING_IOC:
            filling = mt5.ORDER_FILLING_IOC
        else:
            filling = mt5.ORDER_FILLING_RETURN

        request = {
            "action": mt5.TRADE_ACTION_DEAL,
            "symbol": symbol,
            "volume": volume,
            "type": order_type,
            "position": pos.ticket,
            "price": price,
            "deviation": 20,
            "magic": 123456,
            "comment": "AlphaBot close all",
            "type_time": mt5.ORDER_TIME_GTC,
            "type_filling": filling,
        }

        result = mt5.order_send(request)
        if result.retcode == mt5.TRADE_RETCODE_DONE:
            closed.append(result._asdict())
        else:
            errors.append(result._asdict())

    return {"closed": closed, "errors": errors}