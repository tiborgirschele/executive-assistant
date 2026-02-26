#!/bin/bash

echo "=== 1. DEEP SCAN (EXCLUDING /mnt) ==="
for c in ea-daemon openclaw-gateway-tibor openclaw-gateway-liz openclaw-gateway-family-girschele; do
    echo "----------------------------------------"
    echo "Scanning container: $c"
    docker exec -u root "$c" sh -c '
        # Prune completely ignores /mnt, /proc, and /sys to prevent freezing
        find / -type d \( -path /mnt -o -path /proc -o -path /sys \) -prune -o -type f -name "gog" -print > /tmp/gog_paths.txt 2>/dev/null
        
        if [ -s /tmp/gog_paths.txt ]; then
            cat /tmp/gog_paths.txt | while read -r GOG_PATH; do
                echo "✅ Found: $GOG_PATH"
                chmod a+x "$GOG_PATH"
                ln -sf "$GOG_PATH" /usr/local/bin/gog 2>/dev/null
                ln -sf "$GOG_PATH" /usr/bin/gog 2>/dev/null
                echo "✅ Execution rights forced and linked globally."
            done
        else
            echo "⚠️ No gog binary found in this container."
        fi
    '
done

echo -e "\n=== 2. SMOKE TESTS ==="
echo "Testing gog in openclaw-gateway-tibor:"
docker exec openclaw-gateway-tibor sh -c "gog --version || echo '❌ Not working'"

echo -e "\n=== 3. DAEMON LOGS ==="
docker logs --tail 20 ea-daemon
