#!/bin/bash
PASS="rangersofB5"

for c in openclaw-gateway-tibor ea-daemon; do
    echo "=== 🛠️ Fixing $c ==="
    # 1. Force copy binary to both global bin paths
    docker exec -u root openclaw-gateway-tibor cat /home/node/.openclaw/gog_binary > /tmp/gog_tmp
    docker cp /tmp/gog_tmp $c:/usr/bin/gog
    docker cp /tmp/gog_tmp $c:/usr/local/bin/gog
    
    # 2. Fix Linker, Permissions, and Keyring
    docker exec -u root $c sh -c "
        chmod 755 /usr/bin/gog /usr/local/bin/gog && \
        mkdir -p /home/linuxbrew/.linuxbrew/lib && \
        ln -sf /lib64/ld-linux-x86-64.so.2 /home/linuxbrew/.linuxbrew/lib/ld.so && \
        mkdir -p /home/node/.config/gogcli && \
        ln -sf /home/node/.openclaw/gogcli/credentials.json /home/node/.config/gogcli/credentials.json && \
        gog auth keyring set file
    "
done
rm /tmp/gog_tmp
echo "✅ Binaries and Linkers synced."
