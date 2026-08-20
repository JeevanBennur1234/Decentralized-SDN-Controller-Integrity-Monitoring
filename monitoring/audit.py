"""
monitoring/audit.py — Immutable append-only audit log.
Each line is JSON; each entry hashes the previous line (tamper-evident chain).
"""
import json, hashlib, time, os, threading, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import AUDIT_FILE, SNAPSHOT_DIR
from shared.logger import get_logger

log = get_logger("monitoring.audit")

class Audit:
    def __init__(self, cid: str):
        self.cid    = cid
        self._prev  = "0"*64
        self._lock  = threading.Lock()
        os.makedirs(os.path.dirname(AUDIT_FILE), exist_ok=True)
        os.makedirs(SNAPSHOT_DIR, exist_ok=True)
        self.write("AUDIT_START", {"cid": cid})

    def write(self, etype: str, data: dict):
        with self._lock:
            entry = {"ts": time.time(), "cid": self.cid,
                     "type": etype, "data": data, "prev": self._prev}
            line  = json.dumps(entry, sort_keys=True)
            h     = hashlib.sha3_256(line.encode()).hexdigest()
            entry["hash"] = h
            self._prev = h
            try:
                with open(AUDIT_FILE, "a") as f:
                    f.write(json.dumps(entry) + "\n")
            except OSError as e:
                log.warning(f"Audit write failed: {e}")

    def snapshot(self, state: dict) -> str:
        fname = os.path.join(SNAPSHOT_DIR,
                             f"{self.cid}_{int(time.time())}.json")
        json.dump({"ts": time.time(), "cid": self.cid, "state": state},
                  open(fname, "w"), indent=2)
        return fname
