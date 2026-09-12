#!/bin/bash
# scripts/verify.sh — Quick sanity check: are all services reachable?
cd "$(dirname "$0")/.."
source venv/bin/activate 2>/dev/null || true

echo "=== SDN Integrity Monitor — Health Check ==="

check() {
  local name="$1" url="$2"
  if curl -sf "$url" > /dev/null 2>&1; then
    echo "  OK   $name -> $url"
  else
    echo "  FAIL $name -> $url (not reachable)"
  fi
}

check "Dashboard"     "http://localhost:5000/api/status"
check "Prometheus"    "http://localhost:5000/metrics"
check "Ctrl01 Gossip" "http://localhost:9101/gossip/ping"
check "Ctrl02 Gossip" "http://localhost:9102/gossip/ping"
check "Ctrl03 Gossip" "http://localhost:9103/gossip/ping"

echo ""
echo "State file:"
[ -f /tmp/sdn_state.json ] && python3 -c "
import json; s=json.load(open('/tmp/sdn_state.json'))
for cid,c in s.items():
    status='HEALTHY' if c.get('healthy') else 'COMPROMISED'
    print(f'  {cid}: {status} | hash={c.get(\"hash\",\"?\")[:16]}... | pkts={c.get(\"packets\",0)}')
" || echo "  /tmp/sdn_state.json not found (controller not running)"

echo ""
echo "Alert count:"
[ -f /tmp/sdn_alerts.json ] && python3 -c "
import json; a=json.load(open('/tmp/sdn_alerts.json'))
print(f'  {len(a)} alert(s)')
for x in a[-3:]:
    print(f'  [{x.get(\"type\")}] {x.get(\"source\")}: {x.get(\"detail\",\"\")[:60]}')
" || echo "  No alerts file found"

echo ""
echo "Audit log:"
[ -f logs/audit.jsonl ] && \
  echo "  $(wc -l < logs/audit.jsonl) entries in logs/audit.jsonl" || \
  echo "  No audit log yet"
