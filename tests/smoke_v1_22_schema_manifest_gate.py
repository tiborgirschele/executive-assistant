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


def _manifest_rows(manifest_path: pathlib.Path) -> list[str]:
    rows: list[str] = []
    for raw in manifest_path.read_text(encoding="utf-8").splitlines():
        cleaned = raw.split("#", 1)[0].strip()
        if cleaned:
            rows.append(cleaned)
    return rows


def test_schema_manifest_and_docker_e2e_wiring() -> None:
    manifest = ROOT / "ea/schema/runtime_manifest.txt"
    assert manifest.exists(), "runtime schema manifest is required"
    rows = _manifest_rows(manifest)
    assert rows, "runtime schema manifest must not be empty"

    required = {
        "20260303_v1_18_1_runtime_alignment.sql",
        "20260303_v1_18_planner.sql",
        "20260304_v1_20_execution_sessions.sql",
        "20260305_v1_21_approval_gates.sql",
        "20260305_v1_21_provider_outcomes.sql",
        "20260305_v1_22_commitment_runtime_seed.sql",
        "20260305_v1_22_memory_candidates.sql",
        "20260305_v1_22_approval_gate_deadlines.sql",
        "20260305_v1_22_execution_ledger_fields.sql",
    }
    missing = sorted(required - set(rows))
    assert not missing, f"manifest_missing_required:{','.join(missing)}"
    for row in rows:
        assert (ROOT / "ea/schema" / row).exists(), f"manifest_missing_file:{row}"

    docker_e2e = (ROOT / "scripts/docker_e2e.sh").read_text(encoding="utf-8")
    assert "runtime_manifest.txt" in docker_e2e
    assert "SCHEMA_MANIFEST" in docker_e2e
    assert "done < \"${SCHEMA_MANIFEST}\"" in docker_e2e
    assert "SCHEMA_FILES+=(" in docker_e2e
    _pass("v1.22 schema manifest gate wiring")


if __name__ == "__main__":
    test_schema_manifest_and_docker_e2e_wiring()
