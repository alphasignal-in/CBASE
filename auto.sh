#!/bin/bash

# List of assets
ASSETS=("EURUSD" "GBPUSD" "AUDUSD" "USDJPY" "USDCHF" "XAUUSD" "BTCUSD" "ETHUSD" )

# Loop through each asset
for ASSET in "${ASSETS[@]}"; do
    echo "🔹 Fetching candles for $ASSET ..."
    curl -s -X GET "http://44.242.196.239:8000/candles?symbol=$ASSET&timeframe=M1&count=300" \
        -o "data/$ASSET.json"

    echo "⚡ Running bruteforce for $ASSET ..."
    python3.9 finelbrutforce.py "data/$ASSET.json" 

    echo "✅ Completed $ASSET"
    echo "------------------------------------"
    mv strategy.json result/$ASSET-stretegy.json
    cat result/$ASSET-stretegy.json|jq -r '.winrate'
done


# fetch the candels and create stgy json
# chose the best from all jsons based on 