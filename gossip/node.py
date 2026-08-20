"""
gossip/node.py — Push-based P2P gossip protocol.

Every GOSSIP_INTERVAL seconds each controller broadcasts its signed state
to all peers via HTTP POST. Each peer verifies the signature and runs
majority-vote consensus. Offline peers are detected via heartbeat TTL.
"""
import threading, time, requests, json, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.config import GOSSIP_INTERVAL, HEARTBEAT_TTL, get_peers
from shared.events import E
from shared.logger import get_logger

log = get_logger("gossip.node")

class GossipNode:
    def __init__(self, cid: str, agent):
        self.cid        = cid
        self.agent      = agent
        self.peers      = get_peers(cid)
        self.peer_hashes: dict = {}
        self.last_seen:   dict = {}
        self._running   = False
        self._start_time = time.time()   # Grace period reference
        log.info(f"GossipNode {cid} | peers={[p['id'] for p in self.peers]}")

    def start(self):
        self._running = True
        threading.Thread(target=self._gossip_loop, daemon=True, name="gossip").start()
        threading.Thread(target=self._hb_loop,     daemon=True, name="heartbeat").start()

    def stop(self):
        self._running = False

    def receive(self, msg: dict) -> dict:
        """Called by gossip HTTP server when a peer state arrives."""
        pid, phash, sig = msg.get("cid"), msg.get("hash"), msg.get("sig")
        ts,  idx        = msg.get("ts", 0), msg.get("idx", 0)
        if not all([pid, phash, sig]):
            return {"ok": False, "error": "missing fields"}

        self.last_seen[pid] = time.time()
        ok = self.agent.verify_peer(pid, phash, sig, ts, idx)
        if ok:
            self.peer_hashes[pid] = phash
            if self.peer_hashes:
                self.agent.run_consensus(self.peer_hashes.copy())
        return {"ok": ok, "my_hash": self.agent.chain.head}

    def _gossip_loop(self):
        while self._running:
            time.sleep(GOSSIP_INTERVAL)
            state = self.agent.get_signed_state()
            for p in self.peers:
                self._push(p, state)

    def _push(self, peer: dict, state: dict):
        url = f"http://{peer['host']}:{peer['gossip_port']}/gossip/recv"
        try:
            r = requests.post(url, json=state, timeout=3.0)
            log.debug(f"Gossip → {peer['id']} | {r.status_code}")
        except requests.ConnectionError:
            log.debug(f"Peer {peer['id']} unreachable")
        except Exception as e:
            log.warning(f"Gossip error → {peer['id']}: {e}")

    def _hb_loop(self):
        while self._running:
            time.sleep(10)
            now = time.time()
            if now - self._start_time < 75:   # increased grace
                continue
            for p in self.peers:
                pid  = p["id"]
                last = self.last_seen.get(pid, 0)
                if last > 0 and now - last > HEARTBEAT_TTL:
                    self.agent._alert(E.CTRL_OFFLINE, pid,
                                      f"No gossip for {now-last:.0f}s (TTL={HEARTBEAT_TTL}s)",
                                      "HIGH")
