"""
tests/test_chain.py — Unit tests for SHA3-256 hash chain integrity.
Run:  python3 -m pytest tests/ -v
"""
import sys, os, hashlib, json
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest
from integrity.chain import HashChain, GENESIS

class TestHashChain:
    def setup_method(self):
        self.chain = HashChain("test_ctrl")

    def test_genesis_head(self):
        assert self.chain.head == GENESIS
        assert self.chain.height == 0

    def test_single_block(self):
        b = self.chain.add({"event": "BOOT", "ts": 1000.0})
        assert b["hash"] != GENESIS
        assert b["prev"] == GENESIS
        assert self.chain.height == 1
        assert self.chain.head == b["hash"]

    def test_chain_links_correctly(self):
        b1 = self.chain.add({"n": 1})
        b2 = self.chain.add({"n": 2})
        assert b2["prev"] == b1["hash"]
        assert b1["prev"] == GENESIS

    def test_hash_is_deterministic(self):
        """Same state + same prev must always produce same hash."""
        c1, c2 = HashChain("c1"), HashChain("c2")
        state = {"ts": 1234.5, "event": "BOOT", "switches": 0}
        b1 = c1.add(state)
        b2 = c2.add(state)
        assert b1["hash"] == b2["hash"]

    def test_verify_all_clean_chain(self):
        for i in range(20):
            self.chain.add({"n": i, "ts": float(i)})
        assert self.chain.verify_all() is True

    def test_tamper_detected(self):
        for i in range(5):
            self.chain.add({"n": i})
        # Tamper block 2
        self.chain.blocks[2]["state"]["n"] = 9999
        assert self.chain.verify_all() is False

    def test_tamper_prev_hash_detected(self):
        for i in range(5):
            self.chain.add({"n": i})
        self.chain.blocks[1]["prev"] = "a" * 64
        assert self.chain.verify_all() is False

    def test_memory_bounded(self):
        """Chain must not exceed 1000 blocks in memory."""
        for i in range(1200):
            self.chain.add({"n": i})
        assert len(self.chain.blocks) <= 1000
        assert self.chain.height == 1200


class TestHashChainCrypto:
    def test_hash_algorithm_is_sha3_256(self):
        """Verify we really are using SHA3-256, not SHA-256."""
        chain = HashChain("crypto_test")
        state = {"x": 42}
        canon = json.dumps(state, sort_keys=True, separators=(",", ":"))
        expected = hashlib.sha3_256((canon + GENESIS).encode()).hexdigest()
        b = chain.add(state)
        assert b["hash"] == expected

    def test_genesis_is_all_zeros(self):
        assert GENESIS == "0" * 64
        assert len(GENESIS) == 64
