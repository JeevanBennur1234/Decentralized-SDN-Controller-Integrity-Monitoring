#!/bin/bash
# scripts/setup.sh — One-time setup: venv, pip, keys, dirs
set -e
cd "$(dirname "$0")/.."
echo "=== SDN Integrity Monitor — Setup ==="
[ ! -d venv ] && python3 -m venv venv
source venv/bin/activate
echo "[1/3] Installing dependencies..."
pip install --quiet flask flask-socketio flask-cors \
  cryptography requests prometheus-client \
  eventlet ryu 2>/dev/null || \
pip install --quiet flask flask-socketio flask-cors \
  cryptography requests prometheus-client eventlet
echo "[2/3] Generating ECDSA keys..."
python3 -c "
import sys; sys.path.insert(0,'.')
from integrity.signer import ensure_keys
for c in ['ctrl_01','ctrl_02','ctrl_03']:
    ensure_keys(c); print(f'  {c} ok')
"
echo "[3/3] Clearing stale files..."
rm -f /tmp/sdn_state.json /tmp/sdn_alerts.json
echo "Setup complete. Run: bash scripts/start_multi.sh"
