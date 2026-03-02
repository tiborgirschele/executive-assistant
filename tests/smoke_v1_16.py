from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "ea/schema/20260303_v1_16_actions.sql"
TOK = ROOT / "ea/app/telegram/callback_tokens.py"
ORCH = ROOT / "ea/app/action_layer.py"

schema = SCHEMA.read_text(encoding="utf-8")
for table in (
    "action_drafts",
    "action_state_history",
    "approval_requests",
    "approval_decisions",
    "action_callbacks",
    "action_executions",
    "execution_receipts",
    "saga_instances",
    "saga_steps",
    "compensation_events",
):
    assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
print("[SMOKE][HOST][PASS] v1.16 schema tables present")

for path in (TOK, ORCH):
    ast.parse(path.read_text(encoding="utf-8"))
print("[SMOKE][HOST][PASS] v1.16 modules parse")
