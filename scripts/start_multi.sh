#!/bin/bash
# scripts/start_multi.sh
# Starts 3 SDN controllers + dashboard

set -e

cd "$(dirname "$0")/.."

source venv/bin/activate

echo "════════════════════════════════════════════"
echo " SDN Integrity Monitor — Multi Controller "
echo "════════════════════════════════════════════"

# -------------------------------------------------
# Cleanup
# -------------------------------------------------

echo "[*] Cleaning old processes..."
rm -f /tmp/sdn_state.json
rm -f /tmp/sdn_alerts.json
rm -f logs/*.log
pkill -f ryu-manager || true
pkill -f "python3 dashboard/app.py" || true

sleep 2

sudo mn -c > /dev/null 2>&1 || true

rm -f /tmp/sdn_state.json
rm -f /tmp/sdn_alerts.json

mkdir -p logs

# -------------------------------------------------
# Controller 1
# -------------------------------------------------

echo ""
echo "[1/4] Starting ctrl_01"
echo "       OpenFlow : 6633"
echo "       Gossip   : 9101"

CONTROLLER_ID=ctrl_01 \
ryu-manager \
--ofp-tcp-listen-port 6633 \
controller/ryu_controller.py \
> logs/ctrl_01.log 2>&1 &

PID1=$!

echo "       PID      : $PID1"

sleep 3

# -------------------------------------------------
# Controller 2
# -------------------------------------------------

echo ""
echo "[2/4] Starting ctrl_02"
echo "       OpenFlow : 6634"
echo "       Gossip   : 9102"

CONTROLLER_ID=ctrl_02 \
ryu-manager \
--ofp-tcp-listen-port 6634 \
controller/ryu_controller.py \
> logs/ctrl_02.log 2>&1 &

PID2=$!

echo "       PID      : $PID2"

sleep 3

# -------------------------------------------------
# Controller 3
# -------------------------------------------------

echo ""
echo "[3/4] Starting ctrl_03"
echo "       OpenFlow : 6635"
echo "       Gossip   : 9103"

CONTROLLER_ID=ctrl_03 \
ryu-manager \
--ofp-tcp-listen-port 6635 \
controller/ryu_controller.py \
> logs/ctrl_03.log 2>&1 &

PID3=$!

echo "       PID      : $PID3"

sleep 3

# -------------------------------------------------
# Dashboard
# -------------------------------------------------

echo ""
echo "[4/4] Starting dashboard..."

python3 dashboard/app.py \
> logs/dashboard.log 2>&1 &

PID4=$!

echo "       PID      : $PID4"

sleep 5

# -------------------------------------------------
# Verify ports
# -------------------------------------------------

echo ""
echo "[*] Verifying OpenFlow ports..."

sudo netstat -tulnp | grep 663 || true

echo ""
echo "════════════════════════════════════════════"
echo " All services started successfully"
echo "════════════════════════════════════════════"

echo ""
echo "Dashboard:"
echo "  http://localhost:5000"

echo ""
echo "OpenFlow Controllers:"
echo "  ctrl_01 → 6633"
echo "  ctrl_02 → 6634"
echo "  ctrl_03 → 6635"

echo ""
echo "Gossip Ports:"
echo "  9101, 9102, 9103"

echo ""
echo "PIDs:"
echo "  ctrl_01   : $PID1"
echo "  ctrl_02   : $PID2"
echo "  ctrl_03   : $PID3"
echo "  dashboard : $PID4"

echo ""
echo "Run Mininet in NEW terminal:"
echo ""
echo "sudo mn --topo tree,depth=2,fanout=3 \\"
echo "  --controller remote,ip=127.0.0.1,port=6633 \\"
echo "  --switch ovsk,protocols=OpenFlow13"

echo ""
echo "Attack simulation:"
echo ""
echo "source venv/bin/activate"
echo "python3 attacks/simulator.py all"

echo ""
echo "Watch logs:"
echo ""
echo "tail -f logs/ctrl_01.log"
