#!/bin/bash
echo "=== 🚀 1. INJECTING BINARY INTO DAEMON ==="
# We will use the container-to-container copy to be 100% sure we get the right file
docker exec openclaw-gateway-tibor cat /home/node/.openclaw/gog_binary > /tmp/gog_tmp
docker cp /tmp/gog_tmp ea-daemon:/usr/local/bin/gog
rm /tmp/gog_tmp

docker exec -u root ea-daemon sh -c "
    chmod 755 /usr/local/bin/gog && \
    mkdir -p /home/linuxbrew/.linuxbrew/lib && \
    ln -sf /lib64/ld-linux-x86-64.so.2 /home/linuxbrew/.linuxbrew/lib/ld.so
"
echo "✅ Daemon Binary Ready."

echo -e "\n=== 🔑 2. LINKING CREDENTIALS INTO GATEWAY ==="
# We found them at /docker/openclaw-app/credentials.json
docker cp /docker/openclaw-app/credentials.json openclaw-gateway-tibor:/home/node/.config/gogcli/credentials.json

docker exec -u root openclaw-gateway-tibor sh -c "
    chmod 644 /home/node/.config/gogcli/credentials.json && \
    chown node:node /home/node/.config/gogcli/credentials.json
"
echo "✅ Credentials Linked."

echo -e "\n=== 🧪 3. SMOKE TESTS ==="
echo "Testing Daemon Execution:"
docker exec ea-daemon gog --version || echo "❌ Daemon still failing"

echo "Testing Gateway Auth:"
docker exec openclaw-gateway-tibor gog calendar list --account tibor.girschele@gmail.com || echo "❌ Auth still failing"
