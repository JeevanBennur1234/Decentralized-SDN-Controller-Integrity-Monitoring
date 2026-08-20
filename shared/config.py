import os, json
from typing import Dict, List

BASE_DIR     = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KEYS_DIR     = os.path.join(BASE_DIR, "keys")
LOGS_DIR     = os.path.join(BASE_DIR, "logs")
SNAPSHOT_DIR = os.path.join(LOGS_DIR, "snapshots")
STATE_FILE   = "/tmp/sdn_state.json"
ALERT_FILE   = "/tmp/sdn_alerts.json"
AUDIT_FILE   = os.path.join(LOGS_DIR, "audit.jsonl")
DASHBOARD_PORT  = 5000
GOSSIP_BASE     = 9100
CONTROLLERS: Dict[str, dict] = {
    "ctrl_01": {"host": "127.0.0.1", "gossip_port": 9101, "of_port": 6633},
    "ctrl_02": {"host": "127.0.0.1", "gossip_port": 9102, "of_port": 6634},
    "ctrl_03": {"host": "127.0.0.1", "gossip_port": 9103, "of_port": 6635},
}
GOSSIP_INTERVAL   = 5.0
HEARTBEAT_TTL     = 30.0
CONSENSUS_QUORUM  = 0.67
FLOOD_PPS_LIMIT   = 500
REPLAY_WINDOW_S   = 60
SECRET_KEY        = os.environ.get("SDN_SECRET", "sdn-integrity-2026")

def get_cid() -> str:
    return os.environ.get("CONTROLLER_ID", "ctrl_01")

def get_peers(cid: str) -> List[dict]:
    return [{"id": k, **v} for k, v in CONTROLLERS.items() if k != cid]

def ensure_dirs():
    for d in [KEYS_DIR, LOGS_DIR, SNAPSHOT_DIR]:
        os.makedirs(d, exist_ok=True)

ensure_dirs()