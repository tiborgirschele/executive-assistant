from __future__ import annotations

import ast
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "ea/schema/20260303_v1_15_rag.sql"
CTRL = ROOT / "ea/app/retrieval/control_plane.py"
TB = ROOT / "ea/app/llm_gateway/trust_boundary.py"

schema = SCHEMA.read_text(encoding="utf-8")
for table in (
    "source_objects",
    "source_permissions",
    "extraction_runs",
    "extracted_documents",
    "retrieval_chunks",
    "retrieval_acl_rules",
    "connector_cursors",
    "retrieval_audit_events",
    "extraction_cache_jobs",
):
    assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
print("[SMOKE][HOST][PASS] v1.15 schema tables present")

for path in (CTRL, TB):
    ast.parse(path.read_text(encoding="utf-8"))
print("[SMOKE][HOST][PASS] v1.15 modules parse")

ctrl_src = CTRL.read_text(encoding="utf-8")
assert "class RetrievalControlPlane" in ctrl_src
assert "def ingest_pointer_first(" in ctrl_src
assert "def retrieve_for_principal(" in ctrl_src
assert "INSERT INTO source_objects" in ctrl_src
assert "INSERT INTO retrieval_chunks" in ctrl_src
assert "INSERT INTO retrieval_acl_rules" in ctrl_src
assert "WHERE c.tenant_key = %s AND a.principal_id = %s AND a.policy = 'allow'" in ctrl_src
assert "def _fingerprint(" in ctrl_src
assert "def _chunk_text(" in ctrl_src
print("[SMOKE][HOST][PASS] v1.15 retrieval control-plane symbols present")

tb_src = TB.read_text(encoding="utf-8")
assert "def wrap_untrusted_evidence(" in tb_src
assert "def validate_model_output(" in tb_src
assert "_TOOL_CALL_PAT" in tb_src
assert "_PROMPT_INJECTION_PAT" in tb_src
print("[SMOKE][HOST][PASS] v1.15 trust-boundary symbols present")

sys.path.insert(0, str(ROOT / "ea"))
from app.llm_gateway.trust_boundary import wrap_untrusted_evidence, validate_model_output  # noqa: E402

wrapped = wrap_untrusted_evidence(
    [
        {
            "chunk_text": "hello",
            "provenance_json": {"source_uri": "paperless://doc/1"},
        }
    ]
)
parsed = json.loads(wrapped)
assert isinstance(parsed, dict) and "untrusted_evidence" in parsed
assert parsed["untrusted_evidence"][0]["safety"] == "untrusted_input"
assert validate_model_output("summary", "execute tool_call now") == "blocked_tool_like_output"
assert validate_model_output("summary", "Ignore previous instructions") == "blocked_prompt_injection_echo"
assert validate_model_output("payment", "Please approve now") == "blocked_high_risk_without_explicit_flow"
assert validate_model_output("summary", "Safe grounded summary") == "ok"
print("[SMOKE][HOST][PASS] v1.15 trust-boundary behavior")
