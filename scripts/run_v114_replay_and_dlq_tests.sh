#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-/docker/EA}"

if docker compose version >/dev/null 2>&1; then
  DC=(docker compose)
else
  DC=(docker-compose)
fi

echo "[SMOKE][v1.14] Host compile"
python3 -m py_compile \
  "$ROOT/ea/app/evidence_vault/service.py" \
  "$ROOT/ea/app/operator/trust_service.py" \
  "$ROOT/ea/app/repair/replay_worker.py" \
  "$ROOT/tests/smoke_v1_14.py"
python3 "$ROOT/tests/smoke_v1_14.py"

echo "[SMOKE][v1.14] Container trust/replay/dlq flow"
"${DC[@]}" exec -T ea-worker python - <<'PY'
from app.operator.trust_service import TrustOperatorService
from app.repair.replay_worker import process_replay_once

svc = TrustOperatorService()
item_id = svc.create_review_item(
    correlation_id="v114-smoke-1",
    safe_hint={"safe_hint": "needs review", "reason": "low_confidence_ownership"},
    raw_document_ref="telegram:chat:700:message:55:file:x",
)
claim = svc.claim_review_item(review_item_id=item_id, actor_id="op-smoke")
vault_id = svc.store_raw_evidence(
    tenant_key="smoke_tenant",
    object_ref="doc://smoke/1",
    correlation_id="v114-smoke-1",
    payload=b"sensitive raw payload",
)
revealed = svc.reveal_evidence(
    review_item_id=item_id,
    actor_id="op-smoke",
    claim_token=claim,
    vault_object_id=vault_id,
    reason="triage",
)
assert revealed == b"sensitive raw payload"
replay_id = svc.emit_replay(
    review_item_id=item_id,
    document_id="doc-smoke-1",
    pipeline_stage="ingest",
    correlation_id="v114-smoke-1",
)
process_replay_once(replay_event_id=replay_id, success=False, error_text="connector timeout")
process_replay_once(replay_event_id=replay_id, success=False, error_text="connector timeout")
process_replay_once(replay_event_id=replay_id, success=False, error_text="connector timeout")
dead_letter_id = svc.dead_letter_replay(
    replay_event_id=replay_id,
    tenant_key="smoke_tenant",
    failure_code="connector_timeout",
    source_pointer="paperless://doc-smoke-1",
    connector_type="paperless",
    correlation_id="v114-smoke-1",
)
assert dead_letter_id > 0
shredded = svc.vault.crypto_shred(
    tenant_key="smoke_tenant",
    object_ref="doc://smoke/1",
    reason="source_deleted",
)
assert shredded >= 1
try:
    svc.vault.read(vault_object_id=vault_id)
    raise AssertionError("vault object should be unreadable after shred")
except ValueError as e:
    assert "shredded" in str(e)
print("[SMOKE][v1.14][PASS] trust flow, replay, dead-letter, crypto-shred")
PY

echo "[SMOKE][v1.14] PASS"
