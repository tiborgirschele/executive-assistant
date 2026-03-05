#!/usr/bin/env bash
set -euo pipefail

EA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${EA_ROOT}"

if [[ "${1:-}" == "--help" || "${1:-}" == "-h" ]]; then
  cat <<'EOF'
Usage:
  bash scripts/verify_release_assets.sh

Validates presence of required runtime docs, scripts, and schema files.
Exits non-zero when any required asset is missing.
EOF
  exit 0
fi

missing=0

required_files=(
  "README.md"
  "RUNBOOK.md"
  "ARCHITECTURE_MAP.md"
  "HTTP_EXAMPLES.http"
  "CHANGELOG.md"
  "ENVIRONMENT_MATRIX.md"
  "MILESTONE.json"
  "RELEASE_CHECKLIST.md"
  "TASKS_WORK_LOG.md"
  "scripts/deploy.sh"
  "scripts/db_bootstrap.sh"
  "scripts/db_status.sh"
  "scripts/smoke_api.sh"
  "scripts/export_openapi.sh"
  "scripts/diff_openapi.sh"
  "scripts/prune_openapi.sh"
  "scripts/list_endpoints.sh"
  "scripts/version_info.sh"
  "scripts/operator_summary.sh"
  "scripts/support_bundle.sh"
  "scripts/archive_tasks.sh"
  "ea/schema/20260305_v0_2_execution_ledger_kernel.sql"
  "ea/schema/20260305_v0_3_channel_runtime_kernel.sql"
  "ea/schema/20260305_v0_4_policy_decisions_kernel.sql"
)

echo "== verify release assets =="
for f in "${required_files[@]}"; do
  if [[ -f "${f}" ]]; then
    echo "ok: ${f}"
  else
    echo "missing: ${f}" >&2
    missing=1
  fi
done

echo "== verify release docs linkage =="
if grep -Fq "make operator-help" "README.md"; then
  echo "ok: README operator-help reference"
else
  echo "missing: README operator-help reference" >&2
  missing=1
fi

if grep -Fq "Operator Script Help Index" "RUNBOOK.md"; then
  echo "ok: RUNBOOK script help index"
else
  echo "missing: RUNBOOK script help index" >&2
  missing=1
fi

if [[ "${missing}" -ne 0 ]]; then
  echo "release asset verification failed" >&2
  exit 1
fi

echo "all required release assets present"
