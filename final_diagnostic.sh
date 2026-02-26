#!/bin/bash
echo "=== 🔍 OPENCLAW GOG DIAGNOSTIC ==="

for c in openclaw-gateway-tibor ea-daemon; do
    echo "-----------------------------------------------"
    echo "CONTAINER: $c"
    docker exec -u root "$c" sh -c '
        echo "[1] Command Location:"
        GOG_LOC=$(command -v gog)
        if [ -z "$GOG_LOC" ]; then 
            echo "❌ gog NOT in PATH"
        else
            echo "✅ Found at: $GOG_LOC"
            
            echo -e "\n[2] File Details:"
            ls -l "$GOG_LOC"
            file "$GOG_LOC" 2>/dev/null || echo "Can\''t run file command"
            
            echo -e "\n[3] Test Execution:"
            "$GOG_LOC" --version 2>&1 || echo "❌ Execution Failed"
        fi

        echo -e "\n[4] Searching for gogcli (The actual binary name):"
        GOGCLI_LOC=$(command -v gogcli)
        if [ -n "$GOGCLI_LOC" ]; then
            echo "✅ Found gogcli at: $GOGCLI_LOC"
            ls -l "$GOGCLI_LOC"
        else
            echo "❌ gogcli NOT in PATH"
        fi
        
        echo -e "\n[5] Checking for obstructive directories:"
        ls -d /usr/local/bin/gog /usr/bin/gog /home/node/gog 2>/dev/null
    '
done
