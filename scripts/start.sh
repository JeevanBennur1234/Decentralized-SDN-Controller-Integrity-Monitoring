#!/bin/bash
# scripts/start.sh — Start a single controller (ctrl_01) + dashboard
set -e
cd "$(dirname "$0")/.."
source venv/bin/activate
rm -f /tmp/sdn_state.json /tmp/sdn_alerts.json

echo "Starting Ryu controller (ctrl_01)..."
CONTROLLER_ID=ctrl_01 ryu-manager controller/ryu_controller.py \
  --verbose > logs/ctrl_01.log 2>&1 &
echo "  PID $! -> logs/ctrl_01.log"
sleep 2

echo "Starting Dashboard..."
python3 dashboard/app.py > logs/dashboard.log 2>&1 &
echo "  PID $! -> logs/dashboard.log"
sleep 1

echo ""
echo "Services started."
echo "  Dashboard  -> http://localhost:5000"
echo ""
echo "Mininet (new terminal):"
echo "  sudo mn --topo tree,depth=2,fanout=3 \\"
echo "    --controller remote,ip=127.0.0.1,port=6633 \\"
echo "    --switch ovsk,protocols=OpenFlow13"
echo ""
echo "Tail logs: tail -f logs/ctrl_01.log logs/dashboard.log"
