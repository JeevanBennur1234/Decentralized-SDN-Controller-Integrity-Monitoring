"""
tests/test_signer.py — Unit tests for ECDSA P-256 signing and verification.
"""
import sys, os, tempfile
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest

# Patch KEYS_DIR to a temp dir so tests don't write to real keys/
# The signer module captures KEYS_DIR at import time, so patch the module
# global directly (patching shared.config afterwards would have no effect).
import integrity.signer as signer_mod
_tmp = tempfile.mkdtemp()
signer_mod.KEYS_DIR = _tmp

from integrity.signer import generate_keys, sign, verify, ensure_keys

TEST_CID = "test_ctrl"

class TestSigner:
    def setup_method(self):
        generate_keys(TEST_CID)

    def test_sign_returns_hex_string(self):
        sig = sign(b"hello world", TEST_CID)
        assert isinstance(sig, str)
        assert len(sig) > 100      # DER signature is ~70 bytes = 140 hex chars
        assert all(c in "0123456789abcdef" for c in sig)

    def test_verify_valid_signature(self):
        data = b"integrity check"
        sig  = sign(data, TEST_CID)
        assert verify(data, sig, TEST_CID) is True

    def test_verify_wrong_data(self):
        sig = sign(b"original", TEST_CID)
        assert verify(b"tampered", sig, TEST_CID) is False

    def test_verify_forged_signature(self):
        data = b"state data"
        fake_sig = "ab" * 70           # 140-char hex, but not a valid DER sig
        assert verify(data, fake_sig, TEST_CID) is False

    def test_verify_empty_signature(self):
        assert verify(b"data", "", TEST_CID) is False

    def test_ensure_keys_idempotent(self):
        """Calling ensure_keys twice must not regenerate (would break chain)."""
        import os, time
        from integrity.signer import _paths
        priv, _ = _paths(TEST_CID)
        assert os.path.exists(priv), "Private key should exist after setup_method"
        mtime_before = os.path.getmtime(priv)
        time.sleep(0.05)
        ensure_keys(TEST_CID)              # should be a no-op
        mtime_after  = os.path.getmtime(priv)
        assert mtime_before == mtime_after, "Key file should not be modified"

    def test_different_controllers_different_keys(self):
        generate_keys("ctrl_A")
        generate_keys("ctrl_B")
        data = b"shared message"
        sig_a = sign(data, "ctrl_A")
        # sig_a must NOT verify against ctrl_B's public key
        assert verify(data, sig_a, "ctrl_B") is False
