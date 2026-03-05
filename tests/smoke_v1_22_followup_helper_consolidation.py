from __future__ import annotations

import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_followup_helper_wiring_presence() -> None:
    helper_src = (ROOT / "ea/app/planner/followup_seeding.py").read_text(encoding="utf-8")
    runtime_src = (ROOT / "ea/app/intent_runtime.py").read_text(encoding="utf-8")
    callback_src = (ROOT / "ea/app/callback_commands.py").read_text(encoding="utf-8")
    assert "def seed_followups_for_deferred_artifacts(" in helper_src
    assert "DEFERRED_ARTIFACT_TYPES" in helper_src
    assert "seed_followups_for_deferred_artifacts" in runtime_src
    assert "seed_followups_for_deferred_artifacts" in callback_src
    _pass("v1.22 followup helper consolidation wiring")


def test_followup_helper_behavior() -> None:
    import app.planner.followup_seeding as helper

    calls = {"upsert": [], "artifact": [], "followup": []}

    orig_upsert = helper.upsert_commitment
    orig_create_artifact = helper.create_artifact
    orig_create_followup = helper.create_followup

    helper.upsert_commitment = lambda **kwargs: calls["upsert"].append(dict(kwargs or {})) or True
    helper.create_artifact = lambda **kwargs: calls["artifact"].append(dict(kwargs or {})) or "art-helper-1"
    helper.create_followup = lambda **kwargs: calls["followup"].append(dict(kwargs or {})) or "fol-helper-1"
    try:
        seeded = helper.seed_followups_for_deferred_artifacts(
            tenant_key="chat_100284",
            session_id="sess-helper-1",
            commitment_key="travel:chat_100284:sess-helper",
            domain="travel",
            title="Travel follow-up",
            artifacts=[
                {
                    "artifact_type": "travel_decision_pack",
                    "summary": "Route options",
                    "content": {"preview": "A/B"},
                    "note": "Review options now.",
                },
                {
                    "artifact_type": "chat_response",
                    "summary": "ignore",
                },
            ],
            source="test",
        )
    finally:
        helper.upsert_commitment = orig_upsert
        helper.create_artifact = orig_create_artifact
        helper.create_followup = orig_create_followup

    assert calls["upsert"], "expected commitment upsert"
    assert calls["artifact"], "expected deferred artifact persistence"
    assert calls["followup"], "expected followup creation"
    assert list(seeded.get("followup_ids") or []) == ["fol-helper-1"]
    refs = list(seeded.get("output_refs") or [])
    assert "artifact:art-helper-1" in refs
    assert "followup:fol-helper-1" in refs
    _pass("v1.22 followup helper consolidation behavior")


if __name__ == "__main__":
    test_followup_helper_wiring_presence()
    test_followup_helper_behavior()
