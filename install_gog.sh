#!/bin/bash
# Official gogcli release for Linux AMD64
GOG_URL="https://github.com/steipete/gogcli/releases/download/v0.4.5/gogcli_v0.4.5_linux_amd64.tar.gz"

echo "=== 🚀 INSTALLING GOG BINARY TO CONTAINERS ==="

for c in openclaw-gateway-tibor openclaw-gateway-liz openclaw-gateway-family-girschele ea-daemon; do
    echo "----------------------------------------"
    echo "Target: $c"
    
    # Download, extract, and set permissions in one go
    docker exec -u root "$c" sh -c "
        curl -L $GOG_URL | tar -xz -C /usr/local/bin gogcli && \
        chmod 755 /usr/local/bin/gogcli && \
        ln -sf /usr/local/bin/gogcli /usr/local/bin/gog && \
        ln -sf /usr/local/bin/gogcli /usr/bin/gog
    "
    
    echo -e "✅ Installation finished for $c"
done

echo -e "\n=== 🧪 SMOKE TESTS ==="
echo "Testing gog version in gateway:"
docker exec openclaw-gateway-tibor gog --version || echo "❌ Smoke test failed in gateway"

echo -e "\n=== 📊 DAEMON LOGS ==="
docker logs --tail 20 ea-daemon
