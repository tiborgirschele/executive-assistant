from __future__ import annotations

import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_v121_gate_alias_script_and_docs() -> None:
    alias_script = ROOT / "scripts/run_v121_smoke.sh"
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    script_src = alias_script.read_text(encoding="utf-8")
    assert alias_script.exists()
    assert "run_v120_smoke.sh" in script_src
    assert "run_v121_smoke.sh" in readme
    _pass("v1.21 gate alias script/docs alignment")


if __name__ == "__main__":
    test_v121_gate_alias_script_and_docs()
