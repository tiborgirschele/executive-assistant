from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "ea/schema/20260303_v1_14_trust.sql"
VAULT = ROOT / "ea/app/evidence_vault/service.py"
TRUST = ROOT / "ea/app/operator/trust_service.py"
REPLAY = ROOT / "ea/app/repair/replay_worker.py"

schema = SCHEMA.read_text(encoding="utf-8")
for table in (
    "review_claims",
    "evidence_reveals",
    "dead_letter_items",
    "dead_letter_envelopes",
    "evidence_vault_objects",
    "deletion_tombstones",
    "connector_health",
    "breaker_history",
    "operator_audit_events",
):
    assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
print("[SMOKE][HOST][PASS] v1.14 schema tables present")

for path in (VAULT, TRUST, REPLAY):
    ast.parse(path.read_text(encoding="utf-8"))
print("[SMOKE][HOST][PASS] v1.14 modules parse")
