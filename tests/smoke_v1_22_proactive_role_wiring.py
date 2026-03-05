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


def test_proactive_role_wiring() -> None:
    runner_src = (ROOT / "ea/app/runner.py").read_text(encoding="utf-8")
    compose_src = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    role_src = (ROOT / "ea/app/roles/proactive.py").read_text(encoding="utf-8")
    assert 'elif r == "proactive":' in runner_src
    assert "from app.roles.proactive import run_proactive" in runner_src
    assert "ea-proactive:" in compose_src
    assert "- EA_ROLE=proactive" in compose_src
    assert "- proactive" in compose_src
    assert "async def run_proactive()" in role_src
    _pass("v1.22 proactive role wiring")


if __name__ == "__main__":
    test_proactive_role_wiring()
