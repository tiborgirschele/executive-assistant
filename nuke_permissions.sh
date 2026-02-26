#!/bin/bash

echo "=== 1. DEEP SCAN & PERMISSION OVERRIDE ==="
for c in ea-daemon openclaw-gateway-tibor openclaw-gateway-liz openclaw-gateway-family-girschele; do
    echo "Scanning container: $c"
    docker exec -u root "$c" sh -c '
        # 1. Find anything named gog and show us what it is
        echo "Found paths:"
        find / -name "gog" -exec ls -ld {} + 2>/dev/null
        
        # 2. Force executable rights on any FILE named gog
        find / -type f -name "gog" -exec chmod a+x {} + 2>/dev/null
    '
done

echo -e "\n=== 2. SMOKE TESTS ==="
echo "Testing ea-daemon:"
docker exec ea-daemon sh -c "gog --version || echo '❌ Not working here'"

echo "Testing openclaw-gateway-tibor:"
docker exec openclaw-gateway-tibor sh -c "gog --version || echo '❌ Not working here'"

echo -e "\n=== 3. DAEMON LOGS ==="
docker logs --tail 20 ea-daemon
