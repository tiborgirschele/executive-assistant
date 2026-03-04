from __future__ import annotations

import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "ea/schema/20260302_v1_13_onboarding.sql"
EGRESS = ROOT / "ea/app/net/egress_guard.py"
ONBOARD = ROOT / "ea/app/onboarding/service.py"
REGISTRY = ROOT / "ea/app/connectors/registry.py"
PROFILE_CORE = ROOT / "ea/app/intelligence/profile.py"
DOSSIERS = ROOT / "ea/app/intelligence/dossiers.py"
CRITICAL_LANE = ROOT / "ea/app/intelligence/critical_lane.py"

schema = SCHEMA.read_text(encoding="utf-8")
for table in (
    "tenant_invites",
    "onboarding_sessions",
    "principals",
    "channel_bindings",
    "oauth_connections",
    "source_connections",
    "source_test_runs",
    "tenant_provision_jobs",
    "onboarding_audit_events",
    "connector_network_modes",
):
    assert f"CREATE TABLE IF NOT EXISTS {table}" in schema
print("[SMOKE][HOST][PASS] v1.13 schema tables present")

for path in (EGRESS, ONBOARD, REGISTRY):
    src = path.read_text(encoding="utf-8")
    ast.parse(src)
print("[SMOKE][HOST][PASS] v1.13 modules parse")

assert "evaluate_connector_url" in EGRESS.read_text(encoding="utf-8")
onboard_src = ONBOARD.read_text(encoding="utf-8")
assert "class OnboardingService" in onboard_src
assert "def _upsert_channel_binding" in onboard_src
assert "ON CONFLICT DO NOTHING" in onboard_src
assert "DELETE FROM channel_bindings" in onboard_src
assert "CONNECTOR_REGISTRY" in REGISTRY.read_text(encoding="utf-8")
print("[SMOKE][HOST][PASS] v1.13 core symbols present")

for path in (PROFILE_CORE, DOSSIERS, CRITICAL_LANE):
    src = path.read_text(encoding="utf-8")
    ast.parse(src)
print("[SMOKE][HOST][PASS] v1.13 profile intelligence modules parse")

profile_src = PROFILE_CORE.read_text(encoding="utf-8")
assert "class PersonProfileContext" in profile_src
assert "def build_profile_context(" in profile_src
dossiers_src = DOSSIERS.read_text(encoding="utf-8")
assert "class Dossier" in dossiers_src
assert "def build_trip_dossier(" in dossiers_src
critical_src = CRITICAL_LANE.read_text(encoding="utf-8")
assert "class CriticalLaneResult" in critical_src
assert "def build_critical_actions(" in critical_src
print("[SMOKE][HOST][PASS] v1.13 profile intelligence symbols present")
