"""
integrity/agent.py — Core integrity engine embedded in every Ryu controller.

Responsibilities:
  1. Build full state snapshots on every network event
  2. Maintain SHA3-256 hash chain (tamper-evident history)
  3. Sign each block with ECDSA P-256 private key
  4. Write signed state to shared JSON file for dashboard
  5. Detect: floods, abnormal flow rates, replay, consensus failures
  6. Provide get_signed_state() for gossip layer
  7. Receive and verify peer states (verify_peer)
  8. Run trust-based consensus (run_consensus)
"""
import hashlib, json, os, sys, time, threading, requests
try:
    import fcntl                    # Unix file locking (Linux only)
except ImportError:
    fcntl = None                    # Windows/dev fallback: no locking
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from integrity.chain    import HashChain
from integrity.signer   import sign, verify, ensure_keys
from monitoring.audit   import Audit
from shared.config      import (STATE_FILE, ALERT_FILE, FLOOD_PPS_LIMIT,
                                REPLAY_WINDOW_S, get_cid)
from shared.events      import E
from monitoring.anomaly import AnomalyEngine
from shared.logger      import get_logger

log = get_logger("integrity.agent")
_DASH = "http://localhost:5000/api/event"

class IntegrityAgent:
    def __init__(self, cid: str = None):
        self.cid        = cid or get_cid()
        self.chain      = HashChain(self.cid)
        self.audit      = Audit(self.cid)
        self._lock      = threading.Lock()
        self.t0         = time.time()
        self.boot_grace_end = self.t0 + 90   # 90s total grace
        
        # Counters
        self.n_sw       = 0
        self.n_pkt      = 0
        self.n_flow     = 0
        self.n_alert    = 0
        self.mac_table  = {}       # {dpid:{mac:port}}
        
        # Rate windows
        self._pkt_ts    = []
        self._flow_ts   = []
        
        # Peer tracking for replay/rollback protection
        self._peer_last_idx = {}
        
        # Trust scores per peer
        self.trust      = {}
        self._anomaly   = AnomalyEngine(self.cid)

        ensure_keys(self.cid)
        self._flush(E.BOOT)
        self._emit("state", f"[{self.cid}] Agent online — GENESIS")
        log.info(f"IntegrityAgent started for {self.cid}")
        threading.Thread(
            target=self._heartbeat_flush,
            daemon=True
        ).start()

    # ── Recovery ──────────────────────────────────────────────────────

    def reset_alerts(self):
        """Reset alert counter and trust scores → controller returns to HEALTHY."""
        with self._lock:
            self.n_alert = 0
            self.trust   = {pid: 1.0 for pid in self.trust}
        self._flush("RECOVERY")
        self._emit("state", f"[{self.cid}] Recovery — alerts cleared, trust restored")
        self.audit.write("RECOVERY", {"cid": self.cid})
        log.info(f"[{self.cid}] RECOVERY: n_alert=0, trust reset to 1.0")

    # ── Called by Ryu controller ──────────────────────────────────────

    def on_switch_up(self, dpid: int):
        with self._lock:
            self.n_sw += 1
            self.mac_table.setdefault(dpid, {})
        self._flush(f"SWITCH_UP dpid={dpid}")
        self._emit("switch", f"[{self.cid}] Switch s{dpid} connected")
        self.audit.write(E.SWITCH_UP, {"dpid": dpid})

    def on_switch_down(self, dpid: int):
        with self._lock:
            self.n_sw = max(0, self.n_sw - 1)
        self._flush(f"SWITCH_DOWN dpid={dpid}")

    def on_packet_in(self, dpid: int, src: str, dst: str, in_port: int, out_port):
        with self._lock:
            self.n_pkt += 1
            now = time.time()
            self._pkt_ts.append(now)
            self._pkt_ts = [t for t in self._pkt_ts if now - t < 1.0]
            self.mac_table.setdefault(dpid, {})[src] = in_port
            pps = len(self._pkt_ts)
            
        if pps > FLOOD_PPS_LIMIT:
            self._alert(E.FLOOD, self.cid,
                        f"Flood: {pps} pps on dpid={dpid} (limit={FLOOD_PPS_LIMIT})", "HIGH")
        
        # Grace period: skip anomaly detection for first 30s after boot
        if time.time() - self.t0 > 30 and self._anomaly.check("pkt_rate", float(pps)):
            self._alert(E.FLOOD, self.cid,
                        f"Statistical anomaly: pkt_rate={pps:.0f} pps (3-sigma breach)", "MEDIUM")
        
        if self.n_pkt % 10 == 0:
            self._flush(f"PKT count={self.n_pkt}")

    def on_flow_add(self, dpid: int, priority: int, match: str):
        with self._lock:
            self.n_flow += 1
            now = time.time()
            self._flow_ts.append(now)
            self._flow_ts = [t for t in self._flow_ts if now - t < 1.0]
            rate = len(self._flow_ts)
            
        if rate > 50:
            self._alert(E.FLOW_INJECT, self.cid,
                        f"Abnormal flow rate: {rate}/s on dpid={dpid}", "HIGH")
        
        self._flush(f"FLOW_ADD dpid={dpid} pri={priority}")
        self.audit.write(E.FLOW_ADD, {"dpid": dpid, "priority": priority, "match": match})

    # ── Gossip interface ──────────────────────────────────────────────

    def get_signed_state(self) -> dict:
        h   = self.chain.head
        sig = sign(h.encode(), self.cid)
        return {
            "cid": self.cid, "hash": h, "sig": sig,
            "idx": self.chain.height, "ts": time.time(),
            "switches": self.n_sw, "packets": self.n_pkt,
            "flows": self.n_flow, "alerts": self.n_alert,
            "trust": self.trust,
        }

    def verify_peer(self, pid: str, phash: str, sig: str, ts: float, idx: int) -> bool:
        """
        Validates the authenticity and freshness of peer gossip messages.
        Protects against Replay, Rollback, and MITM attacks.
        """
        now = time.time()

        # 1. Timestamp freshness check
        if now - ts > REPLAY_WINDOW_S:
            self._alert(E.REPLAY, pid, f"Stale message from {pid} ({now-ts:.1f}s old)", "MEDIUM")
            return False

        # 2. Replay / rollback protection
        last_idx = self._peer_last_idx.get(pid, -1)
        if idx < last_idx:
            self._alert(E.REPLAY, pid, f"Outdated blockchain idx={idx} < last_idx={last_idx}", "HIGH")
            return False

        self._peer_last_idx[pid] = idx

        # 3. Signature verification
        ok = verify(phash.encode(), sig, pid)
        if not ok:
            self.trust[pid] = max(0.0, self.trust.get(pid, 1.0) - 0.3)
            self._alert(E.SIG_INVALID, pid, f"ECDSA verification failed for {pid}", "HIGH")
            return False

        # 4. Trust increase for valid behavior
        self.trust[pid] = min(1.0, self.trust.get(pid, 1.0) + 0.02)
        return True

    def run_consensus(self, peer_hashes: dict) -> dict:
        """
        Consensus validated by peer responsiveness and local chain integrity.
        """
        healthy = []
        suspicious = []
        total_nodes = len(peer_hashes) + 1 

        for pid, phash in peer_hashes.items():
            if not phash:
                self.trust[pid] = max(0.0, self.trust.get(pid, 1.0) - 0.25)
                suspicious.append(pid)
                self._alert(E.CONSENSUS_FAIL, pid, f"No gossip response from {pid}", "MEDIUM")
                continue

            self.trust[pid] = min(1.0, self.trust.get(pid, 1.0) + 0.02)
            healthy.append(pid)

        chain_ok = self.chain.verify_all()
        if not chain_ok:
            self._alert(E.HASH_MISMATCH, self.cid, "Local blockchain integrity failed", "HIGH")
            return {"ok": False, "reason": "local_chain_invalid"}

        active_nodes = len(healthy) + 1
        quorum = active_nodes / total_nodes >= 0.67

        for pid, score in self.trust.items():
            if score < 0.30 and pid not in suspicious:
                suspicious.append(pid)
                self._alert(E.HASH_MISMATCH, pid, f"Trust score critically low ({score:.2f})", "HIGH")

        return {
            "ok": quorum and chain_ok,
            "healthy": healthy,
            "suspicious": list(set(suspicious)),
            "trust": self.trust,
            "active_nodes": active_nodes,
            "total_nodes": total_nodes,
        }

    # ── Internal ──────────────────────────────────────────────────────

    def _snap(self, event: str) -> dict:
        return {
            "cid":      self.cid,
            "ts":        time.time(),
            "uptime":    round(time.time() - self.t0, 1),
            "switches": self.n_sw,
            "packets":   self.n_pkt,
            "flows":     self.n_flow,
            "alerts":    self.n_alert,
            "mac_sz":    sum(len(v) for v in self.mac_table.values()),
            "event":     event,
            "height":    self.chain.height,
        }

    def _flush(self, event: str):
        snap  = self._snap(event)
        block = self.chain.add(snap)
        sig   = sign(block["hash"].encode(), self.cid)
        
        payload = {
            self.cid: {
                "healthy": (self.n_alert < 2 and self.chain.verify_all()),
                "hash":      block["hash"],
                "sig":       sig,
                "idx":       block["idx"],
                "switches":  self.n_sw,
                "packets":   self.n_pkt,
                "flows":     self.n_flow,
                "alerts":    self.n_alert,
                "ts":        time.time(),
                "event":     event,
                "trust":     self.trust,
                "chain_ok":  True,
            }
        }
        try:
            # Atomic write: render the full merged document in memory, then
            # swap it into place. Readers (the dashboard poller) never observe
            # a half-written file, and it is portable across POSIX and Windows.
            existing = {}
            if os.path.exists(STATE_FILE):
                try:
                    with open(STATE_FILE) as f:
                        existing = json.load(f)
                except Exception:
                    existing = {}
            existing.update(payload)
            tmp = STATE_FILE + ".tmp"
            with open(tmp, "w") as f:
                json.dump(existing, f, indent=2)
                f.flush()
                if hasattr(os, "fsync"):
                    os.fsync(f.fileno())
            os.replace(tmp, STATE_FILE)
        except Exception as e:
            log.warning(f"State write failed: {e}")

    def _alert(self, atype: str, src: str, detail: str, sev: str = "HIGH"):
        now = time.time()
        with self._lock:
            # Skip counting most alerts during boot grace period
            if now < self.boot_grace_end and atype not in (E.FLOOD, E.UNAUTH_SW):
                sev = "MEDIUM"  # don't count toward healthy threshold

            # Only HIGH severity alerts count toward compromise threshold
            if sev == "HIGH" and src == self.cid:
                self.n_alert += 1
        alert = {"type": atype, "source": src, "detail": detail,
                 "sev": sev, "ts": now, "detector": self.cid}
        
        # Persistence logic for alerts
        try:
            alerts = []
            if os.path.exists(ALERT_FILE):
                with open(ALERT_FILE) as f:
                    alerts = json.load(f)
            alerts.append(alert)
            with open(ALERT_FILE, "w") as f:
                json.dump(alerts[-500:], f, indent=2)
        except Exception:
            pass
            
        self.audit.write(atype, alert)
        self._emit("alert", f"[{atype}] {src}: {detail}")
        self._flush(f"ALERT:{atype}")
        log.warning(f"ALERT {atype} | {src} | {detail}")

    def _heartbeat_flush(self):
        """
        Periodically create blockchain snapshots even
        when no packets are flowing through the network.
        """
        while True:
            try:
                self._flush("HEARTBEAT")
            except Exception as e:
                log.warning(f"Heartbeat flush failed: {e}")

            time.sleep(5)

    def _emit(self, kind: str, msg: str):
        def _go():
            try:
                requests.post(_DASH, json={"kind": kind, "message": msg}, timeout=0.5)
            except Exception:
                pass
        threading.Thread(target=_go, daemon=True).start()
