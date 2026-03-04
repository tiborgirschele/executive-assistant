#!/usr/bin/env bash
set -euo pipefail

EA_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DB_CONT="ea-db"
API_CONT="ea-api"

SCHEMAS=(
  "20260302_v1_12_1_foundation.sql"
  "20260302_v1_12_5_mumbrain.sql"
  "v1_12_6_avomap.sql"
  "20260302_v1_13_onboarding.sql"
  "20260303_v1_14_trust.sql"
  "20260303_v1_15_rag.sql"
  "20260303_v1_16_actions.sql"
  "20260303_v1_17_personalization.sql"
  "20260303_v1_18_planner.sql"
  "20260303_v1_18_1_runtime_alignment.sql"
  "20260304_v1_19_2_intelligence_snapshots.sql"
  "20260304_v1_19_2_llm_egress_policies.sql"
  "v1.9_meta_ai.sql"
)

cd "${EA_ROOT}"

apply_schema_with_retry() {
  local sql_path="$1"
  local sql_name="$2"
  local attempts=0
  local max_attempts=5
  local delay_sec=2
  while true; do
    attempts=$((attempts + 1))
    local out_file
    out_file="$(mktemp)"
    if docker exec -i "${DB_CONT}" psql -U postgres -d ea -v ON_ERROR_STOP=1 < "${sql_path}" >"${out_file}" 2>&1; then
      rm -f "${out_file}"
      return 0
    fi
    if grep -E "deadlock detected|could not obtain lock on relation|canceling statement due to lock timeout" "${out_file}" >/dev/null 2>&1; then
      if [[ "${attempts}" -lt "${max_attempts}" ]]; then
        echo "retry ${attempts}/${max_attempts} for ${sql_name} after transient DB lock/deadlock"
        sleep "${delay_sec}"
        rm -f "${out_file}"
        continue
      fi
    fi
    cat "${out_file}"
    rm -f "${out_file}"
    return 1
  done
}

echo "== Design E2E: applying workflow schema chain =="
for s in "${SCHEMAS[@]}"; do
  sql="${EA_ROOT}/ea/schema/${s}"
  if [[ ! -f "${sql}" ]]; then
    echo "Missing schema file: ${sql}"
    exit 1
  fi
  echo "--- apply ${s}"
  apply_schema_with_retry "${sql}" "${s}"
done

echo "== Design E2E: sync test script into API container =="
docker cp "${EA_ROOT}/tests/e2e_design_workflows.py" "${API_CONT}:/tmp/e2e_design_workflows.py"
docker cp "${EA_ROOT}/tests/e2e_v1_12_6_avomap.py" "${API_CONT}:/tmp/e2e_v1_12_6_avomap.py"
docker cp "${EA_ROOT}/tests/e2e_browseract_http_ingress.py" "${API_CONT}:/tmp/e2e_browseract_http_ingress.py"
docker cp "${EA_ROOT}/tests/e2e_browseract_http_to_ready_asset.py" "${API_CONT}:/tmp/e2e_browseract_http_to_ready_asset.py"
docker cp "${EA_ROOT}/tests/real_milestone_suite.py" "${API_CONT}:/tmp/real_milestone_suite.py"

echo "== Design E2E: run all design workflows (onboarding/surveys/trust/rag/actions/personalization/planner/mum) =="
docker exec "${API_CONT}" sh -lc "PYTHONPATH=/app python /tmp/e2e_design_workflows.py"

echo "== Design E2E: run real milestone functional suite =="
docker exec "${API_CONT}" sh -lc "PYTHONPATH=/app python /tmp/real_milestone_suite.py"

echo "== Design E2E: run v1.12.6 AvoMap workflow (candidate/spec/job/asset) =="
docker exec "${API_CONT}" sh -lc "PYTHONPATH=/app python /tmp/e2e_v1_12_6_avomap.py"

echo "== Design E2E: run real HTTP BrowserAct ingress acceptance =="
docker exec "${API_CONT}" sh -lc "PYTHONPATH=/app python /tmp/e2e_browseract_http_ingress.py"

echo "== Design E2E: run full BrowserAct HTTP -> worker -> asset chain =="
docker exec "${API_CONT}" sh -lc "PYTHONPATH=/app python /tmp/e2e_browseract_http_to_ready_asset.py"

echo "PASS: design workflow E2E suite passed"
