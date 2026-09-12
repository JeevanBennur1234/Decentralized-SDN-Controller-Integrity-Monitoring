"""
monitoring/prometheus.py
Prometheus metrics exported at /metrics on port 8000 (or dashboard /metrics).
Import this in dashboard/app.py — already wired in via prometheus_client.
Kept here as a standalone module for documentation / future Grafana dashboards.
"""
from prometheus_client import Counter, Gauge, Histogram, Summary, REGISTRY, Info

# ── Controller metrics ─────────────────────────────────────────────────
ctrl_health  = Gauge("sdn_ctrl_health",       "1=healthy 0=compromised", ["ctrl"])
ctrl_packets = Counter("sdn_ctrl_packets",    "Total packets processed",  ["ctrl"])
ctrl_flows   = Gauge("sdn_ctrl_flows",        "Current flow table size",  ["ctrl"])
ctrl_uptime  = Gauge("sdn_ctrl_uptime_s",     "Controller uptime (s)",    ["ctrl"])
ctrl_alerts  = Counter("sdn_ctrl_alerts",     "Alerts raised",            ["ctrl","type"])

# ── Chain metrics ──────────────────────────────────────────────────────
chain_height = Gauge("sdn_chain_height",      "Hash chain block count",   ["ctrl"])
chain_valid  = Gauge("sdn_chain_valid",       "1=chain intact",           ["ctrl"])

# ── Gossip metrics ─────────────────────────────────────────────────────
gossip_sent  = Counter("sdn_gossip_sent",     "Gossip messages sent",     ["ctrl","peer"])
gossip_recv  = Counter("sdn_gossip_recv",     "Gossip messages received", ["ctrl","peer"])
gossip_fail  = Counter("sdn_gossip_fail",     "Gossip delivery failures", ["ctrl","peer"])

# ── Trust metrics ──────────────────────────────────────────────────────
peer_trust   = Gauge("sdn_peer_trust",        "Peer trust score 0-1",     ["ctrl","peer"])

# ── Network metrics ────────────────────────────────────────────────────
pkt_rate     = Gauge("sdn_pkt_rate_pps",      "Packet rate pps",          ["ctrl"])
flood_events = Counter("sdn_flood_events",    "Flood events detected",    ["ctrl"])

# ── System info ────────────────────────────────────────────────────────
sdn_info     = Info("sdn_system", "SDN Integrity Monitor build info")
sdn_info.info({"version": "1.0", "crypto": "ECDSA-P256", "hash": "SHA3-256"})
