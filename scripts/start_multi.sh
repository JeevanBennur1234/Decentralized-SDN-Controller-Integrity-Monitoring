#!/bin/bash
# scripts/start_multi.sh
# Starts all 3 Ryu controllers and the dashboard, then waits until
# every gossip port is actually listening before returning.
set -e

cd "$(dirname "$0")/.."

source venv/bin/activate

echo "=== SDN Integrity Monitor — Multi-Controller ==="

# -------------------------------------------------
# Cleanup stale processes and state files
# -------------------------------------------------

echo "[*] Cleaning up stale processes and state..."
pkill -f ryu-manager 2>/dev/null || true
pkill -f "python3 dashboard/app.py" 2>/dev/null || true
sleep 1
sudo mn -c > /dev/null 2>&1 || true

rm -f /tmp/sdn_state.json /tmp/sdn_alerts.json
rm -f logs/ctrl_01.log logs/ctrl_02.log logs/ctrl_03.log logs/dashboard.log
mkdir -p logs

# -------------------------------------------------
# Start controllers
# -------------------------------------------------

echo ""
echo "[1/4] Starting ctrl_01  (OF :6633, gossip :9101)"
CONTROLLER_ID=ctrl_01 ryu-manager --ofp-tcp-listen-port 6633 \
    controller/ryu_controller.py > logs/ctrl_01.log 2>&1 &
PID1=$!
echo "      PID: $PID1"

echo ""
echo "[2/4] Starting ctrl_02  (OF :6634, gossip :9102)"
CONTROLLER_ID=ctrl_02 ryu-manager --ofp-tcp-listen-port 6634 \
    controller/ryu_controller.py > logs/ctrl_02.log 2>&1 &
PID2=$!
echo "      PID: $PID2"

echo ""
echo "[3/4] Starting ctrl_03  (OF :6635, gossip :9103)"
CONTROLLER_ID=ctrl_03 ryu-manager --ofp-tcp-listen-port 6635 \
    controller/ryu_controller.py > logs/ctrl_03.log 2>&1 &
PID3=$!
echo "      PID: $PID3"

# -------------------------------------------------
# Wait for all three gossip ports to be listening
# (confirms each controller fully initialised)
# -------------------------------------------------

echo ""
echo "[*] Waiting for controllers to come online..."

wait_port() {
    local port=$1 name=$2 tries=0
    while ! ss -tlnH "sport = :$port" 2>/dev/null | grep -q ":$port"; do
        tries=$((tries + 1))
        if [ $tries -ge 30 ]; then
            echo "    ERROR: $name (port $port) did not start within 30s"
            echo "    Check logs/$name.log for errors"
            exit 1
        fi
        sleep 1
    done
    echo "    $name ready (port $port)"
}

wait_port 9101 ctrl_01
wait_port 9102 ctrl_02
wait_port 9103 ctrl_03

# -------------------------------------------------
# Start dashboard
# -------------------------------------------------

echo ""
echo "[4/4] Starting dashboard..."
python3 dashboard/app.py > logs/dashboard.log 2>&1 &
PID4=$!
echo "      PID: $PID4"

wait_port 5000 dashboard

# -------------------------------------------------
# Summary
# -------------------------------------------------

echo ""
echo "=== All services ready ==="
echo ""
echo "Dashboard:  http://localhost:5000"
echo "OpenFlow:   ctrl_01 :6633  ctrl_02 :6634  ctrl_03 :6635"
echo "Gossip:     ctrl_01 :9101  ctrl_02 :9102  ctrl_03 :9103"
echo "PIDs:       ctrl_01=$PID1  ctrl_02=$PID2  ctrl_03=$PID3  dashboard=$PID4"
echo ""
echo "Start Mininet in a new terminal:"
echo "  sudo python3 scripts/multi_controller.py"
echo ""
echo "Watch logs:"
echo "  tail -f logs/ctrl_01.log logs/ctrl_02.log logs/ctrl_03.log"
