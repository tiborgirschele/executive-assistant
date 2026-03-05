#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/docker/EA}"

# v1.22 currently extends the v1.20+ gate surface; keep this alias script
# for release naming clarity while preserving backward compatibility.
bash "$ROOT/scripts/run_v120_smoke.sh" "$ROOT"
