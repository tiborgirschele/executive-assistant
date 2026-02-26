#!/bin/bash
echo "=== HUNTING THE GHOST COMMAND ==="
docker exec -u root openclaw-gateway-tibor sh -c '
    echo "--- TYPE CHECK ---"
    type gog 2>/dev/null || echo "gog not found by shell type"
    type gogcli 2>/dev/null || echo "gogcli not found by shell type"
    
    echo -e "\n--- PATH CHECK ---"
    IFS=":"
    for p in $PATH; do
        [ -e "$p/gog" ] && ls -ld "$p/gog"
        [ -e "$p/gogcli" ] && ls -ld "$p/gogcli"
    done
    
    echo -e "\n--- VOLUME CHECK ---"
    ls -la /home/node/.config/gog* 2>/dev/null
'
