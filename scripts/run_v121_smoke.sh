#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/docker/EA}"

# v1.21 currently extends the v1.20+ gate surface; keep this alias script
# so release/run naming remains legible while preserving backwards compatibility.
bash "$ROOT/scripts/run_v120_smoke.sh" "$ROOT"
