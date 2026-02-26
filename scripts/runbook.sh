#!/usr/bin/env bash
set -euo pipefail
EA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_PORT="$(grep -E '^EA_HOST_PORT=' "${EA_ROOT}/.env" | tail -n1 | cut -d= -f2- || true)"
HOST_PORT="${HOST_PORT:-8090}"

echo "== ps =="
docker compose ps

echo -e "\n== ea-db logs =="
docker logs ea-db --tail 120

echo -e "\n== ea-daemon logs =="
docker logs ea-daemon --tail 240

echo -e "\n== /health =="
curl -s "http://localhost:${HOST_PORT}/health" || true
echo

echo -e "\n== /debug/audit (50) =="
curl -s "http://localhost:${HOST_PORT}/debug/audit?limit=50" | head -c 8000 || true
echo
