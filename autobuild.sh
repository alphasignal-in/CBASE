docker rm -f $(docker ps -aq)
docker rmi -f $(docker images -q)
ASSETS=("EURUSD" "GBPUSD" "AUDUSD"  "XAUUSD" "BTCUSD" "ETHUSD" )
for ASSET in "${ASSETS[@]}"; do
cp Livetrade.py $ASSET 
docker build -t dexterquazi/golive:$ASSET $ASSET 
done
docker login -u dexterquazi -p "##Love##1"
for ASSET in "${ASSETS[@]}"; do
docker push dexterquazi/golive:$ASSET 
done