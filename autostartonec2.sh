# sudo su
# yum install docker -y && systemctl start docker
yum install git -y
yum install docker -y && systemctl start docker
git clone https://github.com/alphasignal-in/GUI.git
cd GUI
docker build -t gui .
docker run -itd --name GUI  -p 80:80 -p 8080:8080 -p 8888:8888 -v /var/run/docker.sock:/var/run/docker.sock gui
ASSETS=("EURUSD" "GBPUSD" "AUDUSD"  "XAUUSD" "BTCUSD" "ETHUSD" )

for ASSET in "${ASSETS[@]}"; do
docker run -itd --name $ASSET dexterquazi/golive:$ASSET 
done
