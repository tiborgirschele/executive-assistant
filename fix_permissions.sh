#!/bin/bash

echo "=== 1. FIXING GOG PERMISSIONS ==="
# Fix EA Daemon (just in case it attempts local execution)
docker exec -u root ea-daemon sh -c "chmod a+x \$(which gog 2>/dev/null) 2>/dev/null" || true

# Fix all OpenClaw Gateways
for container in openclaw-gateway-tibor openclaw-gateway-liz openclaw-gateway-family-girschele; do
    echo "Granting executable rights to 'gog' in $container..."
    docker exec -u root $container sh -c "chmod a+x \$(which gog 2>/dev/null) 2>/dev/null || chmod a+x /usr/local/bin/gog 2>/dev/null || chmod a+x /usr/bin/gog 2>/dev/null" || true
done

echo -e "\n=== 2. SMOKE TEST: GOG EXECUTION ==="
echo "Can the container execute the gog binary now?"
docker exec openclaw-gateway-tibor gog --version || echo "❌ Smoke test failed: gog still not executing."

echo -e "\n=== 3. DAEMON LOGS ==="
docker logs --tail 20 ea-daemon
