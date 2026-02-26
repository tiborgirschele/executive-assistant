#!/usr/bin/env bash
set -euo pipefail
EA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
HOST_PORT="$(grep -E '^EA_HOST_PORT=' "${EA_ROOT}/.env" | tail -n1 | cut -d= -f2- || true)"
HOST_PORT="${HOST_PORT:-8090}"

echo "== Smoke: health =="
curl -fsS "http://localhost:${HOST_PORT}/health" && echo

echo "== Smoke: audit endpoint =="
curl -fsS "http://localhost:${HOST_PORT}/debug/audit?limit=5" | head -c 4000; echo

echo "== Smoke: Telegram connectivity (bot getMe) =="
TG_TOKEN="$(grep -E '^EA_TELEGRAM_BOT_TOKEN=' "${EA_ROOT}/.env" | tail -n1 | cut -d= -f2- || true)"
if [[ -z "${TG_TOKEN}" || "${TG_TOKEN}" == "PUT_YOUR_TELEGRAM_BOT_TOKEN_HERE" ]]; then
  echo "!! EA_TELEGRAM_BOT_TOKEN not set; skipping Telegram smoke."
  exit 0
fi
curl -fsS "https://api.telegram.org/bot${TG_TOKEN}/getMe" | head -c 2000; echo
