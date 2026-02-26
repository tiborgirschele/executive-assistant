#!/bin/bash

echo "=== 1. DEEP SEARCH & REPAIR OF GOG BINARY ==="
for c in openclaw-gateway-tibor openclaw-gateway-liz openclaw-gateway-family-girschele ea-daemon; do
    echo "----------------------------------------"
    echo "Scanning container: $c"
    docker exec -u root "$c" sh -c '
        # Search the entire filesystem for gog or gogcli
        GOG_PATH=$(find / -type f \( -name "gog" -o -name "gogcli" \) 2>/dev/null | grep -v "/proc/" | grep -v "/sys/" | head -n 1)
        
        if [ -n "$GOG_PATH" ]; then
            echo "✅ Found binary at: $GOG_PATH"
            # Force execute permissions
            chmod a+x "$GOG_PATH"
            # Symlink it into the global PATH so docker exec always finds it
            ln -sf "$GOG_PATH" /usr/local/bin/gog
            ln -sf "$GOG_PATH" /usr/bin/gog
            echo "✅ Permissions restored and globally linked!"
        else
            echo "⚠️ No gog binary found in this container."
        fi
    '
done

echo -e "\n=== 2. SMOKE TESTS ==="
echo "Testing gog in openclaw-gateway-tibor..."
docker exec openclaw-gateway-tibor gog --version || echo "❌ Smoke test failed: gog still not executing."

echo -e "\n=== 3. DAEMON LOGS ==="
docker logs --tail 30 ea-daemon
