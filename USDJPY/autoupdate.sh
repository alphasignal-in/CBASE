#!/bin/sh
# autoupdate.sh - runs in an infinite loop to refresh strategy every hour

while true
do
    ASSET=$(basename "$PWD")
    echo "$(date): Fetching candles for $ASSET..."

    curl -s -X GET "http://172.31.35.179:8000/candles?symbol=$ASSET&timeframe=M1&count=300" \
        -o "$ASSET.json"

    # run compiled bruteforce to generate strategy.json
    # make sure finelbrutforce.pyc exists (compiled)
    echo "$(date): Running finelbrutforce..."
    python3 finelbrutforce.pyc "$ASSET.json" || python3 finelbrutforce.pyc "$ASSET.json"

    # move generated strategy into LIVE.json for livetrader
    if [ -f strategy.json ]; then
        mv strategy.json LIVE.json
        echo "$(date): LIVE.json updated for asset : $ASSET"
    else
        echo "$(date): strategy.json not found after bruteforce run"
    fi

    # sleep 1 hour (3600s)
    sleep 120
done