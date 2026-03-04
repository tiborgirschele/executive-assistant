#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/docker/EA}"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

echo "[v1.19] Building shared ea-os image and recreating services"
"${DC[@]}" build ea-api
"${DC[@]}" up -d --force-recreate ea-api ea-worker ea-poller ea-outbox ea-event-worker

echo "[v1.19] Running smoke checks"
"$ROOT/scripts/run_v119_smoke.sh" "$ROOT"

echo "[v1.19] DONE"
