"""
integrity/chain.py
SHA3-256 hash chain.  block[n].hash = SHA3_256(canon(state[n]) + block[n-1].hash)
Changing ANY past state invalidates ALL subsequent hashes.
"""
import hashlib, json, time, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shared.logger import get_logger

log = get_logger("integrity.chain")
GENESIS = "0" * 64

class HashChain:
    def __init__(self, cid: str):
        self.cid    = cid
        self.head   = GENESIS
        self.height = 0
        self.blocks = []          # last 1000 blocks in memory

    def add(self, state: dict) -> dict:
        canon    = json.dumps(state, sort_keys=True, separators=(",",":"))
        new_hash = hashlib.sha3_256((canon + self.head).encode()).hexdigest()
        block    = {"idx": self.height, "cid": self.cid,
                    "state": state, "prev": self.head,
                    "hash": new_hash, "ts": time.time()}
        self.head    = new_hash
        self.height += 1
        self.blocks.append(block)
        if len(self.blocks) > 1000:
            self.blocks.pop(0)
        return block

    def verify_all(self) -> bool:
        prev = GENESIS
        for b in self.blocks:
            if b["prev"] != prev:
                return False
            canon = json.dumps(b["state"], sort_keys=True, separators=(",",":"))
            if hashlib.sha3_256((canon+prev).encode()).hexdigest() != b["hash"]:
                return False
            prev = b["hash"]
        return True
