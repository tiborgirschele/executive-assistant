#!/bin/bash
PASS="rangersofB5"
JSON='{"client_id":"103036758852-3q4sihh9b8kf1l7c1p6cd7u297tbs0a2.apps.googleusercontent.com","client_secret":"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","project_id":"openclaw-concierge","auth_uri":"https://accounts.google.com/o/oauth2/auth","token_uri":"https://oauth2.googleapis.com/token","auth_provider_x509_cert_url":"https://www.googleapis.com/oauth2/v1/certs","redirect_uris":["http://localhost"]}'

# The target containers
TENANTS=("ea-daemon" "openclaw-gateway-liz" "openclaw-gateway-family-girschele")

echo "=== 🚀 REPLICATING FIXES TO TENANTS ==="

# Grab the working binary from tibor's container to the host temporarily
docker exec openclaw-gateway-tibor cat /usr/bin/gog > /tmp/gog_sync

for c in "${TENANTS[@]}"; do
    # Check if container exists and is running before trying to fix it
    if ! docker ps --format '{{.Names}}' | grep -q "^${c}$"; then
        echo "⚠️  Skipping $c (Container not running or does not exist)"
        continue
    fi

    echo "--> 🛠️ Patching $c..."
    
    # 1. Inject Binary
    docker cp /tmp/gog_sync $c:/usr/bin/gog
    docker cp /tmp/gog_sync $c:/usr/local/bin/gog
    
    # 2. Fix Linker, Permissions, Credentials, and Keyring
    docker exec -u root $c /bin/sh -c "
        chmod 755 /usr/bin/gog /usr/local/bin/gog && \
        mkdir -p /home/linuxbrew/.linuxbrew/lib && \
        ln -sf /lib64/ld-linux-x86-64.so.2 /home/linuxbrew/.linuxbrew/lib/ld.so && \
        mkdir -p /home/node/.config/gogcli /root/.config/gogcli && \
        echo '$JSON' > /home/node/.config/gogcli/credentials.json && \
        echo '$JSON' > /root/.config/gogcli/credentials.json && \
        chown -R node:node /home/node/.config/gogcli 2>/dev/null || true && \
        GOG_KEYRING_PASSWORD=$PASS gog auth keyring set file
    "
    echo "✅ $c fully patched."
done

rm /tmp/gog_sync

echo -e "\n=== 🧪 REQUIRED MANUAL AUTH (SMOKE TESTS) ==="
echo "You must run these commands manually to link each specific Google account:"
echo ""
echo "1. For Liz:"
echo "docker exec -it -e GOG_KEYRING_PASSWORD=$PASS openclaw-gateway-liz gog auth add LIZ_EMAIL_HERE@gmail.com --services all --manual"
echo ""
echo "2. For Family:"
echo "docker exec -it -e GOG_KEYRING_PASSWORD=$PASS openclaw-gateway-family-girschele gog auth add FAMILY_EMAIL_HERE@gmail.com --services all --manual"

echo -e "\n=== 📊 DAEMON LOGS ==="
docker logs --tail 20 ea-daemon
