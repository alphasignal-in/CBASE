#!/bin/sh
# start.sh - runs auto updater in the background, then starts the live trader (compiled)

# run autoupdate in background (it will call compiled bruteforce)
sh ./autoupdate.sh &

# give autoupdate some time if needed
sleep 20

# run compiled Livetrade (adjust name if yours differs)
# Run compiled .pyc rather than .py (we compiled with -b)
python3 Livetrade.pyc true