"""
dashboard/app.py
Flask + Flask-SocketIO real-time dashboard.

Background thread reads STATE_FILE + ALERT_FILE every second
and pushes diffs to all connected browsers over WebSocket.
Browser never needs to poll — all updates are server-pushed.

Endpoints:
  GET  /              HTML dashboard
  POST /api/event     Controller posts log events
  GET  /api/state     Current controller states (JSON)
  GET  /api/alerts    Alert history
  GET  /api/events    Event log
  GET  /api/history   Packet rate history for chart
  GET  /metrics       Prometheus scrape
"""
import json, os, sys, time, threading
from collections import deque
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask            import Flask, jsonify, request, render_template_string
from flask_socketio   import SocketIO, emit
from prometheus_client import Counter, Gauge, generate_latest, CONTENT_TYPE_LATEST

from shared.config import STATE_FILE, ALERT_FILE, DASHBOARD_PORT, SECRET_KEY, CONTROLLERS
from shared.logger import get_logger

log = get_logger("dashboard")

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY
sio = SocketIO(app, cors_allowed_origins="*", async_mode="eventlet",
               logger=False, engineio_logger=False)

# Prometheus
prom_pkt    = Counter("sdn_packets_total",   "Packets",   ["ctrl"])
prom_alert  = Counter("sdn_alerts_total",    "Alerts",    ["type"])
prom_health = Gauge(  "sdn_ctrl_health",     "Health",    ["ctrl"])
prom_trust  = Gauge(  "sdn_trust",           "Trust",     ["ctrl","peer"])

# Memory stores
events  : deque = deque(maxlen=500)
_pkt_hist: deque = deque(maxlen=120)
_prev_alert_n = 0
_seen_alert_keys: set = set()

# ── HTML Dashboard ────────────────────────────────────────────────────
# UI loaded inline (no external file dependency at runtime)
with open(os.path.join(os.path.dirname(__file__), "ui.html")) as _f:
    DASHBOARD_HTML = _f.read()

def _ev(kind: str, msg: str) -> dict:
    e = {"kind": kind, "msg": msg, "ts": time.time()}
    events.append(e)
    return e

_ev("state", "Dashboard online — waiting for controller...")

# ── State poller (background thread) ─────────────────────────────────
def _poller():
    global _prev_alert_n
    prev_mtime = 0
    while True:
        try:
            # State file
            if os.path.exists(STATE_FILE):
                mt = os.stat(STATE_FILE).st_mtime
                if mt != prev_mtime:
                    prev_mtime = mt
                    with open(STATE_FILE) as f:
                        state = json.load(f)
                    sio.emit("state", state)
                    # Update Prometheus + pkt history
                    total = 0
                    for cid, c in state.items():
                        prom_health.labels(ctrl=cid).set(1 if c.get("healthy") else 0)
                        total += c.get("packets", 0)
                        for pid, sc in (c.get("trust") or {}).items():
                            prom_trust.labels(ctrl=cid, peer=pid).set(sc)
                    _pkt_hist.append({"ts": time.time(), "n": total})
                    sio.emit("history", list(_pkt_hist)[-60:])

            # Alert file
            if os.path.exists(ALERT_FILE):
                with open(ALERT_FILE) as f:
                    alerts = json.load(f)
                if len(alerts) != _prev_alert_n:
                    new = alerts[_prev_alert_n:]
                    _prev_alert_n = len(alerts)
                    for a in new:
                        key = f"{a.get('type')}:{a.get('ts')}"
                        if key not in _seen_alert_keys:
                            _seen_alert_keys.add(key)
                            sio.emit("alert", a)
                            e = _ev("alert", f"[{a.get('type')}] {a.get('source','?')}: "
                                             f"{(a.get('detail',''))[:90]}")
                            sio.emit("event", e)
                            prom_alert.labels(type=a.get("type","?")).inc()
        except Exception as ex:
            log.debug(f"Poller: {ex}")
        time.sleep(1.0)

threading.Thread(target=_poller, daemon=True, name="poller").start()

# ── WebSocket handlers ────────────────────────────────────────────────
@sio.on("connect")
def _conn():
    log.info(f"Client connected {request.sid}")
    # Send current snapshot on connect
    try:
        with open(STATE_FILE) as f:
            emit("state", json.load(f))
    except Exception:
        pass
    try:
        with open(ALERT_FILE) as f:
            for a in json.load(f)[-30:]:
                emit("alert", a)
    except Exception:
        pass
    for e in list(events)[-60:]:
        emit("event", e)

# ── REST API ──────────────────────────────────────────────────────────
@app.route("/api/event", methods=["POST"])
def api_event():
    d = request.get_json(silent=True) or {}
    e = _ev(d.get("kind","state"), d.get("message",""))
    sio.emit("event", e)
    return jsonify({"ok": True})

@app.route("/api/reset", methods=["POST"])
def api_reset():
    """Reset all alerts and restore controllers to healthy state."""
    global _prev_alert_n, _seen_alert_keys
    # Clear alerts file
    try:
        with open(ALERT_FILE, "w") as f:
            json.dump([], f)
    except Exception:
        pass
    # Reset state file — mark all controllers as healthy
    try:
        if os.path.exists(STATE_FILE):
            with open(STATE_FILE, "r") as f:
                state = json.load(f)
            for cid in state:
                state[cid]["healthy"] = True
                state[cid]["alerts"]  = 0
            with open(STATE_FILE, "w") as f:
                json.dump(state, f, indent=2)
            sio.emit("state", state)
    except Exception:
        pass
    # Reset dashboard memory
    _prev_alert_n = 0
    _seen_alert_keys = set()
    e = _ev("state", "RECOVERY: all alerts cleared, controllers restored to HEALTHY")
    sio.emit("event", e)
    sio.emit("clear_alerts", {})
    return jsonify({"ok": True, "message": "All alerts cleared, controllers restored"})

@app.route("/api/state")
def api_state():
    try:    return jsonify(json.load(open(STATE_FILE)))
    except: return jsonify({})

@app.route("/api/alerts")
def api_alerts():
    try:    return jsonify(json.load(open(ALERT_FILE))[-100:])
    except: return jsonify([])

@app.route("/api/events")
def api_events():
    return jsonify(list(events)[-100:])

@app.route("/api/history")
def api_history():
    return jsonify(list(_pkt_hist))

@app.route("/metrics")
def api_metrics():
    return generate_latest(), 200, {"Content-Type": CONTENT_TYPE_LATEST}

@app.route("/api/status")
def api_status():
    return jsonify({"status": "ok", "controllers": list(CONTROLLERS.keys())})

@app.route("/")
def index():
    return render_template_string(DASHBOARD_HTML,
                                  ctrls=list(CONTROLLERS.keys()))

if __name__ == "__main__":
    print(f"\nSDN Dashboard -> http://localhost:{DASHBOARD_PORT}\n")
    sio.run(app, host="0.0.0.0", port=DASHBOARD_PORT, allow_unsafe_werkzeug=True,
            debug=False, use_reloader=False)
