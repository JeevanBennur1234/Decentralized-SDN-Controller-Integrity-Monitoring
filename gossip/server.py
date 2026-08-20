"""
gossip/server.py — HTTP server that receives gossip from peer controllers.
Each controller runs one instance on its own gossip_port.
"""
import threading, os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from flask import Flask, request, jsonify
from shared.config import CONTROLLERS
from shared.logger import get_logger

log = get_logger("gossip.server")

def run_gossip_server(node, host: str = "0.0.0.0"):
    """Start the gossip HTTP server in a background daemon thread."""
    port = CONTROLLERS.get(node.cid, {}).get("gossip_port", 9101)
    app  = Flask(f"gossip_{node.cid}")
    app.logger.disabled = True

    @app.route("/gossip/recv", methods=["POST"])
    def recv():
        data = request.get_json(silent=True) or {}
        return jsonify(node.receive(data))

    @app.route("/gossip/ping", methods=["GET"])
    def ping():
        return jsonify({
            "id":   node.cid,
            "hash": node.agent.chain.head[:16] + "...",
            "height": node.agent.chain.height,
        })

    @app.route("/gossip/peers", methods=["GET"])
    def peers():
        return jsonify({
            "peers":      [p["id"] for p in node.peers],
            "last_seen":  node.last_seen,
            "peer_hashes": {k: v[:16]+"..." for k, v in node.peer_hashes.items()},
        })

    t = threading.Thread(
        target=lambda: app.run(host=host, port=port,
                               debug=False, use_reloader=False),
        daemon=True,
        name=f"gossip-srv-{node.cid}",
    )
    t.start()
    log.info(f"Gossip server [{node.cid}] → 0.0.0.0:{port}")
