from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def _service_blocks(compose_src: str) -> dict[str, str]:
    blocks: dict[str, str] = {}
    pattern = re.compile(r"(?ms)^  ([a-z0-9-]+):\n(.*?)(?=^  [a-z0-9-]+:|\Z)")
    for match in pattern.finditer(compose_src):
        service = str(match.group(1) or "").strip()
        body = str(match.group(2) or "")
        if service:
            blocks[service] = body
    return blocks


def test_compose_role_services_align_with_runner() -> None:
    compose_src = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    runner_src = (ROOT / "ea/app/runner.py").read_text(encoding="utf-8")
    blocks = _service_blocks(compose_src)

    expected_role_services = {
        "ea-api": "api",
        "ea-poller": "poller",
        "ea-worker": "worker",
        "ea-outbox": "outbox",
        "ea-event-worker": "event_worker",
        "ea-proactive": "proactive",
    }

    for service, role in expected_role_services.items():
        block = blocks.get(service)
        assert block is not None, f"missing service block: {service}"
        assert f"EA_ROLE={role}" in block, f"{service} must declare EA_ROLE={role}"
        assert f'elif r == "{role}":' in runner_src or f'if r == "{role}":' in runner_src, (
            f"runner missing role branch for {role}"
        )

        if "command:" in block:
            assert "python -m app.runner" in block, f"{service} command must route through app.runner"

    # Non-role service checks keep topology clear.
    teable = blocks.get("ea-teable-sync") or ""
    sim_user = blocks.get("ea-sim-user") or ""
    assert "EA_ROLE=" not in teable
    assert "EA_ROLE=" not in sim_user

    _pass("v1.22 compose/runner role topology alignment")


if __name__ == "__main__":
    test_compose_role_services_align_with_runner()
