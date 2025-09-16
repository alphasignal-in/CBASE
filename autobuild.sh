ASSETS=("EURUSD" "GBPUSD" "AUDUSD"  "XAUUSD" "BTCUSD" "ETHUSD" )
for ASSET in "${ASSETS[@]}"; do
docker build -t dexterquazi/golive:$ASSET $ASSET 
cp Livetrade.py $ASSET 
done
docker login -u dexterquazi -p "##Love##1"
for ASSET in "${ASSETS[@]}"; do
docker push dexterquazi/golive:$ASSET 
done