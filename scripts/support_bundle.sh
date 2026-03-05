#!/usr/bin/env bash
set -euo pipefail

EA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${EA_ROOT}"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

OUT_DIR="${EA_ROOT}/artifacts"
mkdir -p "${OUT_DIR}"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
OUT_FILE="${OUT_DIR}/support_bundle_${STAMP}.txt"
TAIL_LINES="${SUPPORT_LOG_TAIL_LINES:-300}"

{
  echo "== Support Bundle =="
  echo "generated_utc=$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  echo

  echo "-- version info --"
  bash scripts/version_info.sh || true
  echo

  echo "-- compose ps --"
  "${DC[@]}" ps || true
  echo

  echo "-- ea-api logs (tail ${TAIL_LINES}) --"
  "${DC[@]}" logs --tail "${TAIL_LINES}" ea-api || true
  echo

  echo "-- ea-db logs (tail ${TAIL_LINES}) --"
  "${DC[@]}" logs --tail "${TAIL_LINES}" ea-db || true
  echo

  echo "-- queued task snapshot --"
  awk '/^## Queue/{flag=1;next}/^## In Progress/{flag=0}flag' TASKS_WORK_LOG.md || true
} > "${OUT_FILE}"

echo "support bundle written: ${OUT_FILE}"
