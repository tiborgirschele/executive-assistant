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


def test_capability_registry_module_presence() -> None:
    src = (ROOT / "ea/app/skills/capability_registry.py").read_text(encoding="utf-8")
    assert "class CapabilityContract" in src
    assert "CAPABILITY_REGISTRY" in src
    assert "def capability_or_raise(" in src
    assert "def list_capabilities(" in src
    assert "def capabilities_for_task(" in src
    _pass("v1.19.4 capability registry module presence")


def test_capability_registry_contains_ltd_inventory() -> None:
    from app.skills.capability_registry import CAPABILITY_REGISTRY, list_capabilities

    expected = {
        "apix_drive",
        "oneair",
        "prompting_systems",
        "undetectable",
        "involve_me",
        "ai_magicx",
        "one_min_ai",
        "avomap",
        "metasurvey",
        "paperguide",
        "vizologi",
        "peekshot",
        "approvethis",
        "browseract",
    }
    missing = [key for key in sorted(expected) if key not in CAPABILITY_REGISTRY]
    assert not missing, f"missing capabilities: {missing}"
    rows = list_capabilities()
    keys = {str(r.get("key")) for r in rows}
    assert expected.issubset(keys)
    _pass("v1.19.4 capability inventory contract")


def test_capability_task_lookup_contract() -> None:
    from app.skills.capability_registry import capabilities_for_task

    travel = set(capabilities_for_task("travel_rescue"))
    assert "oneair" in travel
    intake = set(capabilities_for_task("collect_structured_intake"))
    assert "involve_me" in intake
    assert "metasurvey" in intake
    assert capabilities_for_task("unknown_task_zzz") == []
    _pass("v1.19.4 capability task lookup contract")


if __name__ == "__main__":
    test_capability_registry_module_presence()
    test_capability_registry_contains_ltd_inventory()
    test_capability_task_lookup_contract()
