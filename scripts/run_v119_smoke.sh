#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/docker/EA}"

echo "[SMOKE][v1.19] Host compile"
python3 -m py_compile \
  "$ROOT/ea/app/intelligence/profile.py" \
  "$ROOT/ea/app/intelligence/dossiers.py" \
  "$ROOT/ea/app/intelligence/future_situations.py" \
  "$ROOT/ea/app/intelligence/readiness.py" \
  "$ROOT/ea/app/intelligence/critical_lane.py" \
  "$ROOT/ea/app/intelligence/modes.py" \
  "$ROOT/ea/app/intelligence/preparation_planner.py" \
  "$ROOT/tests/run_incoming_v119_pack.py" \
  "$ROOT/tests/smoke_v1_19_future_intelligence_pack.py"

echo "[SMOKE][v1.19] Incoming contract-pack smoke"
python3 "$ROOT/tests/smoke_v1_19_future_intelligence_pack.py"

if [[ "${EA_SKIP_FULL_GATES:-0}" != "1" ]]; then
  echo "[SMOKE][v1.19] Running full docker gate suite"
  "$ROOT/scripts/docker_e2e.sh"
else
  echo "[SMOKE][v1.19] Skipping full docker gate suite (EA_SKIP_FULL_GATES=1)"
fi

echo "[SMOKE][v1.19] PASS"
