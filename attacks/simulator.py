"""
attacks/simulator.py — Targeted SDN attack simulation framework.

Usage:

python3 attacks/simulator.py ctrl_01
python3 attacks/simulator.py ctrl_02
python3 attacks/simulator.py ctrl_03

python3 attacks/simulator.py reset
"""

import json
import hashlib
import os
import sys
import time
import random
import requests

sys.path.insert(
    0,
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from shared.config import STATE_FILE, ALERT_FILE
from shared.events import E

DASH = "http://localhost:5000/api/event"


# ─────────────────────────────────────────────
# Dashboard Event
# ─────────────────────────────────────────────

def _post(kind, msg):
    try:
        requests.post(
            DASH,
            json={
                "kind": kind,
                "message": msg
            },
            timeout=1
        )
    except:
        pass


# ─────────────────────────────────────────────
# Alert Writer
# ─────────────────────────────────────────────

def _alert(atype, src, detail, sev="HIGH"):

    data = []

    try:
        if os.path.exists(ALERT_FILE):
            data = json.load(open(ALERT_FILE))
    except:
        pass

    data.append({
        "type": atype,
        "source": src,
        "detail": detail,
        "sev": sev,
        "ts": time.time(),
        "detector": "simulator"
    })

    json.dump(
        data,
        open(ALERT_FILE, "w"),
        indent=2
    )

    _post(
        "alert",
        f"[{atype}] {src}: {detail}"
    )

    print(f"   ⚡ {atype} | {detail}")


# ─────────────────────────────────────────────
# Load State
# ─────────────────────────────────────────────

def _state():

    if not os.path.exists(STATE_FILE):
        print(f"[ERROR] {STATE_FILE} missing")
        sys.exit(1)

    return json.load(open(STATE_FILE))


def _save(s):
    json.dump(
        s,
        open(STATE_FILE, "w"),
        indent=2
    )


# ─────────────────────────────────────────────
# Targeted Hash Tampering Attack
# ─────────────────────────────────────────────

def compromise_controller(target):

    print("\n========================================")
    print(f"   Targeted Integrity Attack → {target}")
    print("========================================")

    s = _state()

    if target not in s:
        print(f"[ERROR] Controller {target} not found")
        return

    # Generate forged hash
    fake_hash = hashlib.sha3_256(
        f"forged-{target}-{time.time()}".encode()
    ).hexdigest()

    print(f"\n[1] Hash Tampering")
    print(f"    Target : {target}")
    print(f"    Old Hash: {s[target]['hash'][:20]}...")

    # Compromise ONLY target controller
    s[target]["hash"] = fake_hash
    s[target]["healthy"] = False
    s[target]["alerts"] = s[target].get("alerts", 0) + 1

    # Fake invalid signature
    fake_sig = "".join(
        random.choices(
            "0123456789abcdef",
            k=140
        )
    )

    s[target]["sig"] = fake_sig

    # Save original values before corruption
    original_hash = s[target]["hash"]
    original_sig = s[target]["sig"]
    
    # Apply attack
    _save(s)
    _alert(
        E.HASH_MISMATCH,
        target,
        f"SHA3-256 chain head forged for {target}"
    )
    _alert(
        E.SIG_INVALID,
        target,
        f"ECDSA signature validation failed for {target}"
    )
    print("\n[!] Controller compromised for 10 seconds...")
    time.sleep(10)
    
    # Reload latest state
    s = _state()

    # Automatically restore controller
    if target in s:
        s[target]["hash"] = original_hash
        s[target]["sig"] = original_sig
        s[target]["healthy"] = True
        s[target]["alerts"] = 0

        _save(s)

        print(f"\n[✓] {target} automatically restored")

    print(f"\n[✓] {target} marked COMPROMISED")
    print("\nDashboard:")
    print("   http://localhost:5000")


# ─────────────────────────────────────────────
# Reset System
# ─────────────────────────────────────────────

def reset():

    print("\n========================================")
    print("   Resetting Dashboard State")
    print("========================================")

    # Clear alerts
    json.dump([], open(ALERT_FILE, "w"))

    # Restore controller state
    if os.path.exists(STATE_FILE):

        try:
            s = json.load(open(STATE_FILE))

            for cid in s:

                s[cid]["healthy"] = True
                s[cid]["alerts"] = 0

            json.dump(
                s,
                open(STATE_FILE, "w"),
                indent=2
            )

        except:
            pass

    # Notify dashboard
    try:
        requests.post(
            "http://localhost:5000/api/reset",
            timeout=2
        )
    except:
        pass

    print("\n[✓] All controllers restored to HEALTHY")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

if __name__ == "__main__":

    print("=" * 56)
    print("   SDN Integrity Monitor — Attack Simulator")
    print("=" * 56)

    if len(sys.argv) < 2:

        print("\nUsage:\n")
        print("   python3 attacks/simulator.py ctrl_01")
        print("   python3 attacks/simulator.py ctrl_02")
        print("   python3 attacks/simulator.py ctrl_03")
        print("   python3 attacks/simulator.py reset\n")

        sys.exit(1)

    cmd = sys.argv[1]

    if cmd == "reset":
        reset()

    elif cmd in ["ctrl_01", "ctrl_02", "ctrl_03"]:
        compromise_controller(cmd)

    else:
        print(f"\n[ERROR] Invalid controller: {cmd}")

    print("\n========================================")
