#!/bin/bash
echo "=== 🛠️ FIXING GOG PATH COUPLING ==="

for c in openclaw-gateway-tibor openclaw-gateway-liz openclaw-gateway-family-girschele ea-daemon; do
    echo "----------------------------------------"
    echo "Processing: $c"
    
    # Find the real path of gog or gogcli, ignoring cloud mounts
    REAL_PATH=$(docker exec "$c" find / -type f \( -name "gog" -o -name "gogcli" \) -not -path "/mnt/*" -not -path "/proc/*" 2>/dev/null | head -n 1)

    if [ -z "$REAL_PATH" ]; then
        echo "⚠️  Binary not found in $c"
    else
        echo "✅ Found binary at: $REAL_PATH"
        # Force executable permissions and link it to the global path
        docker exec -u root "$c" sh -c "
            chmod +x '$REAL_PATH'
            ln -sf '$REAL_PATH' /usr/local/bin/gog
            ln -sf '$REAL_PATH' /usr/bin/gog
        "
        echo "✅ Globally linked as 'gog'"
    fi
done

echo -e "\n=== 🧪 SMOKE TEST ==="
docker exec openclaw-gateway-tibor gog --version || echo "❌ Smoke test failed"

echo -e "\n=== 📊 DAEMON LOGS ==="
docker logs --tail 20 ea-daemon
