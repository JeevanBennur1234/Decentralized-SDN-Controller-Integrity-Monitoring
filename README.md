# 🔐 Decentralized SDN Controller Integrity Monitoring

**KLE Technological University · Department of CSE · VI Semester Minor Project 2026**

![CI](https://github.com/JeevanBennur1234/Decentralized-SDN-Controller-Integrity-Monitoring/actions/workflows/ci.yml/badge.svg)
![Python](https://img.shields.io/badge/python-3.8%2B-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![OpenFlow](https://img.shields.io/badge/OpenFlow-v1.3-brightgreen)

A production-grade, distributed SDN security platform that monitors the integrity
of Software-Defined Network controllers in real time using cryptographic hash
chaining, ECDSA digital signatures, and a peer-to-peer gossip consensus protocol.

> **TL;DR** — Every SDN controller keeps a tamper-evident SHA3-256 hash chain of
> its own state, signs it with an ECDSA P-256 key, and broadcasts it to peer
> controllers. Peers verify signatures and freshness, score each other's trust,
> and detect 8 classes of attacks — all without any centralized coordinator.

---

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                   DECENTRALIZED CONTROL PLANE                │
│                                                             │
│  ┌──────────────┐  gossip  ┌──────────────┐  gossip        │
│  │   ctrl_01    │◄────────►│   ctrl_02    │◄──────┐        │
│  │  Ryu + Agent │          │  Ryu + Agent │       │        │
│  │  port 6633   │          │  port 6634   │       │        │
│  └──────┬───────┘          └──────┬───────┘       │        │
│         │ gossip                  │            ┌───┴──────┐ │
│         └────────────────────────┼───────────►│  ctrl_03 │ │
│                                  │            │  port    │ │
│  Writes /tmp/sdn_state.json      │            │  6635    │ │
│         │                        │            └──────────┘ │
└─────────┼────────────────────────┼─────────────────────────┘
          │                        │
          ▼                        ▼
    OpenFlow 1.3            OpenFlow 1.3
   ┌──────────────────────────────────────┐
   │     Mininet: s1 → s2,s3,s4 → h1-h9 │
   └──────────────────────────────────────┘
          │
          ▼
   Flask Dashboard (port 5000)
   WebSocket (Socket.IO) → browser
```

### Key algorithms

| Algorithm | Where used | Purpose |
|-----------|-----------|---------|
| SHA3-256 chain | `integrity/chain.py` | Tamper-evident state history |
| ECDSA P-256 | `integrity/signer.py` | Authenticate each state block |
| Push gossip | `gossip/node.py` | Broadcast state to all peers |
| Majority vote | `integrity/agent.py` | 2-of-3 consensus |
| EWMA 3-sigma | `monitoring/anomaly.py` | Statistical flood/poisoning detection |
| Replay detection | `integrity/agent.py` | Block stale/rollback messages |

---

## File Structure

```
sdn_final/
├── controller/
│   └── ryu_controller.py    L2 switch + integrity + gossip entry point
├── integrity/
│   ├── agent.py             Core monitoring engine (hash, sign, alert, consensus)
│   ├── chain.py             SHA3-256 chained block structure
│   └── signer.py            ECDSA P-256 key management
├── gossip/
│   ├── node.py              P2P push-gossip + heartbeat TTL
│   └── server.py            HTTP server for receiving peer state
├── dashboard/
│   ├── app.py               Flask + Socket.IO backend
│   └── ui.html              Dark dashboard (WebSocket client)
├── monitoring/
│   ├── anomaly.py           EWMA statistical anomaly detection
│   └── audit.py             Immutable signed audit log (tamper-evident)
├── attacks/
│   └── simulator.py         8-scenario attack simulation framework
├── shared/
│   ├── config.py            Central configuration (ports, paths, thresholds)
│   ├── events.py            Event type constants
│   └── logger.py            Structured logging
├── scripts/
│   ├── setup.sh             One-time install: venv + pip + keys
│   ├── start.sh             Launch single controller + dashboard
│   ├── start_multi.sh       Launch 3 controllers + dashboard
│   ├── verify.sh            Health-check all services
│   ├── mininet_topo.py      Custom Mininet topology
│   └── multi_controller.py  Mininet with 3 remote controllers
├── tests/                   Pytest unit + integration suite (38 tests)
├── configs/
│   ├── prometheus.yml       Prometheus scrape config
│   └── default.yaml         YAML mirror of shared/config.py
├── keys/                    Auto-generated ECDSA .pem files (git-ignored)
├── logs/                    Runtime logs + audit.jsonl + snapshots/ (git-ignored)
├── Dockerfile
├── docker-compose.yml       Dashboard + controllers + Prometheus + Grafana
├── pyproject.toml           Package metadata + pytest configuration
└── requirements.txt
```

---

## Quick Start

These instructions assume a **Linux** host (Ubuntu 20.04/22.04 recommended) with
Python 3.8+, since Mininet and Ryu require it.

### 1. Setup (once)

```bash
cd sdn_final
bash scripts/setup.sh
```

### 2. Run tests (optional but recommended)

```bash
source venv/bin/activate
python -m pytest tests/ -v
```

### 3. Start everything — single controller

```bash
bash scripts/start.sh
```

This launches `ctrl_01` (OpenFlow :6633, gossip :9101) and the dashboard
(http://localhost:5000) in the background.

### 4. Start a Mininet topology (new terminal)

```bash
sudo mn --topo tree,depth=2,fanout=3 \
        --controller remote,ip=127.0.0.1,port=6633 \
        --switch ovsk,protocols=OpenFlow13
# inside Mininet CLI:
mininet> pingall
mininet> net
```

### 5. Simulate attacks (new terminal)

```bash
source venv/bin/activate
python3 attacks/simulator.py all    # run all 8 attacks
python3 attacks/simulator.py 1      # a specific attack
python3 attacks/simulator.py reset  # clear alerts
```

### Multi-controller mode (3 controllers)

```bash
bash scripts/start_multi.sh          # ctrl_01/02/03 + dashboard
```

Each controller runs its own gossip server on ports 9101/9102/9103 and gossips
its signed state every 5 seconds; consensus runs on every peer state received.

### Verify everything is healthy

```bash
bash scripts/verify.sh
```

### Docker deployment

```bash
docker compose up --build
# Dashboard :5000 · Prometheus :9090 · Grafana :3000
```

---

## Attack Scenarios

| # | Attack | Detection mechanism |
|---|--------|---------------------|
| 1 | Hash Tampering | Local blockchain `verify_all()` fails |
| 2 | ECDSA Signature Forgery | `verify()` returns False (invalid DER) |
| 3 | Malicious Flow Injection | Abnormal flow rate > 50/s detected |
| 4 | Replay Attack | Rollback / stale block index rejected |
| 5 | Controller Offline | No gossip heartbeat for >30s |
| 6 | Packet Flood DoS | Packet rate > 500 pps on any switch |
| 7 | Fake/Rogue Controller | Unknown controller_id / invalid signature |
| 8 | Unauthorized Switch | DPID not in authorised topology |

---

## Dashboard Features

- **WebSocket live updates** — no page refresh ever needed
- **Controller table** — health, chain hash (head), block index, trust state
- **Real-time alert list** — severity, type, source, detail, timestamp
- **Live event stream** — every switch connect, packet, flow, gossip event
- **Trust score bars** — per-controller peer trust (0–100%), decays on violation
- **Topology SVG** — live tree topology with active link highlighting
- **Prometheus** — `/metrics` endpoint for Grafana integration

---

## Viva / Presentation Points

### Innovation

1. **SHA3-256 chained blocks** — not just hashing state, but chaining blocks so
   any past tampering is retroactively detectable.
2. **Per-controller ECDSA keys** — each controller cryptographically proves its
   identity; no centralised trust authority needed.
3. **Push gossip with consensus** — controllers cross-verify each other without
   any coordination server — true decentralisation.
4. **8-vector attack simulator** — demonstrates all OWASP-style SDN attack
   categories with a single command.

### Algorithm explanation (for viva)

> *"Our hash chain works like a mini blockchain: each block's hash depends on
> both the current state AND the previous block's hash. If an attacker changes
> block 5, block 5's hash changes, which changes block 6's hash, which changes
> block 7's hash — the tamper propagates and becomes visible at the chain head.
> Peers who independently compute the same state get the same hash; a mismatch
> triggers a HASH_MISMATCH consensus failure."*

### Limitations (be honest — professors respect this)

- Gossip uses HTTP, not mTLS — production would use gRPC with mutual TLS.
- Consensus is 2-of-3 majority; Raft or PBFT would be stronger for N>3.
- No automatic remediation — alerts are detected but not acted upon.
- Single-machine demo; real deployment needs Docker Swarm or Kubernetes.

### Future enhancements

- Raft consensus protocol replacing simple majority vote
- Lightweight blockchain anchoring state hashes to Ethereum (every 1000 blocks)
- ML-based anomaly detection (LSTM on packet rate time series)
- RBAC dashboard login with JWT
- mTLS for gossip channel (prevent MITM on controller network)

---

## Troubleshooting

**Mininet "Unable to contact remote controller"**
→ Start Ryu BEFORE running Mininet. Wait for "All subsystems online".

**Dashboard shows blank table**
→ State file not yet written. Check `ryu-manager` is running without error.

**`ryu-manager` ImportError**
→ `pip install ryu` inside venv. Some systems need `pip install --pre ryu`.

**Gossip servers conflict on same port**
→ 3 controllers on one machine must use ports 9101, 9102, 9103.
  Check `shared/config.py` CONTROLLERS dict.

**`flask-socketio` WebSocket fails**
→ `pip install eventlet` — Socket.IO needs an async worker.

---

## Contributing

Fork the repo, make your change, and open a pull request. Please keep the
existing code style, add/adjust tests for any logic you touch, and make sure
`python -m pytest tests/` passes locally before submitting.

---

## License

This project is licensed under the [MIT License](LICENSE).

---

*Built with Ryu, Mininet, Flask-SocketIO, and way too much coffee. ☕*