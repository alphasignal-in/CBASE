IP="http://172.31.35.179:8000"

curl "$IP/balance"

curl "$IP/candles?symbol=XAUUSD&timeframe=M1&count=10"

curl -X POST "http://172.31.35.179:8000/trade" \
     -H "Content-Type: application/json" \
     -d '{"symbol":"BTCUSD","action":"BUY","lot":0.1}'

     curl -X POST "http://172.31.35.179:8000/trade" \
     -H "Content-Type: application/json" \
     -d '{"symbol":"ETHUSD","action":"BUY","lot":0.1}'

     curl -X POST "http://172.31.35.179:8000/trade" \
     -H "Content-Type: application/json" \
     -d '{"symbol":"ETHUSD","action":"BUY","lot":0.1}'


     curl "http://172.31.35.179:8000/symbol_info?symbol=ETHUSD"


     curl "http://172.31.35.179:8000/can_trade?symbol=ETHUSD"


     curl -X POST "http://172.31.35.179:8000/trade" \
     -H "Content-Type: application/json" \
     -d '{
           "symbol": "ETHUSD",
           "action": "BUY",
           "lot": 0.01
         }'


curl -X POST "http://172.31.35.179:8000/trade" \
  -H "Content-Type: application/json" \
  -d '{"symbol":"ETHUSD","action":"BUY","lot":0.01,"sl":4500.0,"tp":4700.0}'


curl -X POST "http://172.31.35.179:8000/close_trade/?ticket=748441"

curl -X POST "http://172.31.35.179:8000/close_trade/" \
  -H "Content-Type: application/json" \
  -d '{"ticket": 748899}'


  curl -s "http://172.31.35.179:8000/symbol_info?symbol=USDJPY"
curl -s "http://172.31.35.179:8000/candles?symbol=USDJPY&timeframe=M1&count=1"

curl -X POST "http://172.31.35.179:8000/trade" \
  -H "Content-Type: application/json" \
  -d '{
        "symbol": "USDJPY",
        "action": "BUY",
        "lot": 0.1,
        "sl": 146.998854,
        "tp": 147.21957299999997
      }'
      147.182