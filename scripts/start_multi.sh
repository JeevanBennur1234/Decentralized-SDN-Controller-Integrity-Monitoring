#!/bin/bash
# scripts/start_multi.sh
# Starts all 3 SDN controllers + dashboard

set -e

cd "$(dirname "$0")/.."

source venv/bin/activate

echo "=== SDN Integrity Monitor — Multi-Controller ==="

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
echo "[1/4] Starting ctrl_01  (OF :6633, gossip :9101)"

CONTROLLER_ID=ctrl_01 \
ryu-manager \
--ofp-tcp-listen-port 6633 \
controller/ryu_controller.py \
> logs/ctrl_01.log 2>&1 &

PID1=$!
echo "       PID: $PID1"

sleep 3

# -------------------------------------------------
# Controller 2
# -------------------------------------------------

echo ""
echo "[2/4] Starting ctrl_02  (OF :6634, gossip :9102)"

CONTROLLER_ID=ctrl_02 \
ryu-manager \
--ofp-tcp-listen-port 6634 \
controller/ryu_controller.py \
> logs/ctrl_02.log 2>&1 &

PID2=$!
echo "       PID: $PID2"

sleep 3

# -------------------------------------------------
# Controller 3
# -------------------------------------------------

echo ""
echo "[3/4] Starting ctrl_03  (OF :6635, gossip :9103)"

CONTROLLER_ID=ctrl_03 \
ryu-manager \
--ofp-tcp-listen-port 6635 \
controller/ryu_controller.py \
> logs/ctrl_03.log 2>&1 &

PID3=$!
echo "       PID: $PID3"

sleep 3

# -------------------------------------------------
# Dashboard
# -------------------------------------------------

echo ""
echo "[4/4] Starting dashboard..."

python3 dashboard/app.py \
> logs/dashboard.log 2>&1 &

PID4=$!
echo "       PID: $PID4"

sleep 5

# -------------------------------------------------
# Verify ports
# -------------------------------------------------

echo ""
echo "[*] Verifying OpenFlow ports..."
sudo netstat -tulnp | grep 663 || true

echo ""
echo "=== All services started ==="
echo ""
echo "Dashboard:  http://localhost:5000"
echo ""
echo "OpenFlow:   ctrl_01 :6633  ctrl_02 :6634  ctrl_03 :6635"
echo "Gossip:     ctrl_01 :9101  ctrl_02 :9102  ctrl_03 :9103"
echo ""
echo "PIDs:  ctrl_01=$PID1  ctrl_02=$PID2  ctrl_03=$PID3  dashboard=$PID4"
echo ""
echo "Start Mininet in a new terminal:"
echo "  sudo python3 scripts/multi_controller.py"
echo ""
echo "Attack simulation (new terminal):"
echo "  source venv/bin/activate"
echo "  python3 attacks/simulator.py ctrl_01"
echo ""
echo "Watch logs:"
echo "  tail -f logs/ctrl_01.log logs/ctrl_02.log logs/ctrl_03.log"
