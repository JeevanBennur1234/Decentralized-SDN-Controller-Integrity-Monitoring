"""
tests/test_agent.py — Integration tests for the IntegrityAgent.

Note: the agent module captures file paths from shared.config at import
time, so the isolation below must patch the module-level globals
(integrity.agent.STATE_FILE / ALERT_FILE) rather than shared.config.
"""
import sys, os, json, tempfile, time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

# Redirect all file I/O to temp files for isolation.
# The agent module captures the paths from shared.config at import time,
# so we patch the module-level globals directly.
import integrity.agent    as agent_mod
import monitoring.audit   as audit_mod
import integrity.signer   as signer_mod

from integrity.agent import IntegrityAgent
from shared.events import E

_counter = [0]


class TestIntegrityAgent:
    def setup_method(self):
        # A fresh temp dir per test so a background heartbeat thread from a
        # previous agent can never race a later test's file-backed asserts.
        _counter[0] += 1
        self.tmp = tempfile.mkdtemp(prefix=f"agent_test_{_counter[0]}_")
        signer_mod.KEYS_DIR    = self.tmp
        agent_mod.STATE_FILE   = os.path.join(self.tmp, "state.json")
        agent_mod.ALERT_FILE   = os.path.join(self.tmp, "alerts.json")
        audit_mod.AUDIT_FILE   = os.path.join(self.tmp, "audit.jsonl")
        audit_mod.SNAPSHOT_DIR = self.tmp
        self.agent = IntegrityAgent(cid="test_01")

    def test_boot_writes_state_file(self):
        assert os.path.exists(agent_mod.STATE_FILE)
        with open(agent_mod.STATE_FILE) as f:
            state = json.load(f)
        assert "test_01" in state
        assert state["test_01"]["healthy"] is True

    def test_switch_connect_increments_counter(self):
        self.agent.on_switch_up(dpid=1)
        with open(agent_mod.STATE_FILE) as f:
            state = json.load(f)
        assert state["test_01"]["switches"] == 1

    def test_packet_in_increments_counter(self):
        for i in range(10):
            self.agent.on_packet_in(1, f"00:00:00:00:00:{i:02x}",
                                    "ff:ff:ff:ff:ff:ff", 1, None)
        assert self.agent.n_pkt == 10

    def test_high_alert_increments_anomaly_count(self):
        assert self.agent.n_alert == 0
        self.agent._alert(E.FLOOD, self.agent.cid, "unit test alert", "HIGH")
        assert self.agent.n_alert == 1

    def test_remote_alert_does_not_count_against_local(self):
        # Alerts attributed to a peer must not compromise THIS controller.
        self.agent._alert(E.FLOOD, "ctrl_02", "peer flood", "HIGH")
        assert self.agent.n_alert == 0

    def test_alert_written_to_file(self):
        self.agent._alert("HASH_MISMATCH", "ctrl_02", "test mismatch")
        with open(agent_mod.ALERT_FILE) as f:
            alerts = json.load(f)
        assert any(a["type"] == "HASH_MISMATCH" for a in alerts)

    def test_chain_head_changes_on_state_update(self):
        h1 = self.agent.chain.head
        self.agent.on_switch_up(1)
        h2 = self.agent.chain.head
        assert h1 != h2

    def test_signed_state_has_required_fields(self):
        s = self.agent.get_signed_state()
        for key in ["cid", "hash", "sig", "idx", "ts", "switches", "packets"]:
            assert key in s, f"Missing key: {key}"

    def test_verify_peer_rejects_fake_signature(self):
        fake_hash = "a" * 64
        fake_sig  = "b" * 140
        result = self.agent.verify_peer("ctrl_02", fake_hash, fake_sig,
                                        time.time(), 0)
        assert result is False

    def test_verify_peer_accepts_valid_signature(self):
        from integrity.signer import generate_keys, sign as _sign
        generate_keys("ctrl_02")
        digest = self.agent.chain.head.encode()
        valid = _sign(digest, "ctrl_02")
        assert self.agent.verify_peer("ctrl_02", self.agent.chain.head,
                                      valid, time.time(), 5) is True

    def test_verify_peer_rejects_rollback(self):
        # A peer whose block index moves backwards is replaying old state.
        from integrity.signer import generate_keys, sign as _sign
        generate_keys("ctrl_02")
        digest = self.agent.chain.head.encode()
        valid = _sign(digest, "ctrl_02")
        assert self.agent.verify_peer("ctrl_02", self.agent.chain.head,
                                      valid, time.time(), 42) is True
        # Same content but an older index must be rejected.
        assert self.agent.verify_peer("ctrl_02", self.agent.chain.head,
                                      valid, time.time(), 41) is False

    def test_consensus_flags_missing_peer(self):
        result = self.agent.run_consensus({"ctrl_02": None})
        assert "ctrl_02" in result["suspicious"]
        assert result["ok"] is False

    def test_consensus_has_expected_keys(self):
        result = self.agent.run_consensus({"ctrl_02": self.agent.chain.head})
        for key in ["ok", "healthy", "suspicious", "trust",
                    "active_nodes", "total_nodes"]:
            assert key in result

    def test_consensus_detects_local_tamper(self):
        for i in range(3):
            self.agent.chain.add({"n": i})
        self.agent.chain.blocks[0]["state"]["n"] = 9999
        result = self.agent.run_consensus({})
        assert result["ok"] is False
        assert result["reason"] == "local_chain_invalid"

    def test_trust_score_degrades_on_bad_sig(self):
        for i in range(3):
            self.agent.verify_peer("ctrl_02", "a" * 64, "b" * 140,
                                   time.time(), i)
        trust = self.agent.trust.get("ctrl_02", 1.0)
        assert trust < 0.9    # trust must have dropped

    def test_health_becomes_false_after_alerts(self):
        # Two HIGH self-attributed alerts compromise the controller.
        self.agent._alert(E.FLOOD, self.agent.cid, "flood 1", "HIGH")
        self.agent._alert(E.FLOOD, self.agent.cid, "flood 2", "HIGH")
        with open(agent_mod.STATE_FILE) as f:
            state = json.load(f)
        assert state["test_01"]["healthy"] is False