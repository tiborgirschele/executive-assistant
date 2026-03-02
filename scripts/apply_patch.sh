#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/docker/EA}"
MILESTONE="${EA_MILESTONE:-custom}"
SQL_FILE="${EA_SQL_FILE:-}"
SMOKE_CMD="${EA_SMOKE_CMD:-}"
EXTRA_CMD="${EA_EXTRA_CMD:-}"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

echo "[$MILESTONE] apply runner start"
if [ -n "$SQL_FILE" ]; then
  echo "[$MILESTONE] applying schema: $SQL_FILE"
  docker exec -i ea-db sh -c 'psql -v ON_ERROR_STOP=1 -U "$POSTGRES_USER" -d "$POSTGRES_DB"' < "$SQL_FILE"
fi

echo "[$MILESTONE] building shared ea-os image and recreating worker/poller"
"${DC[@]}" build ea-api
"${DC[@]}" up -d --force-recreate ea-worker ea-poller

if [ -n "$EXTRA_CMD" ]; then
  echo "[$MILESTONE] extra step"
  bash -lc "$EXTRA_CMD"
fi

if [ -n "$SMOKE_CMD" ]; then
  echo "[$MILESTONE] smoke step"
  bash -lc "$SMOKE_CMD"
fi

echo "[$MILESTONE] apply runner done"
