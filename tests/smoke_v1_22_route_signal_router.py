from __future__ import annotations

import asyncio
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
for path in (str(ROOT), str(EA_DIR)):
    if path not in sys.path:
        sys.path.insert(0, path)


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_route_signal_router_wiring() -> None:
    router_src = (ROOT / "ea/app/update_router.py").read_text(encoding="utf-8")
    signal_src = (ROOT / "ea/app/router_signals.py").read_text(encoding="utf-8")
    assert "from app.router_signals import build_route_signal" in router_src
    assert 'msg["_ea_route_signal"] = build_route_signal(msg)' in router_src
    assert "def build_route_signal(" in signal_src
    _pass("v1.22 route-signal router wiring")


def test_route_signal_router_behavior() -> None:
    from app.update_router import route_update

    captured: dict[str, object] = {"intent": None, "command": None}

    async def _on_callback(cb):
        return None

    async def _on_command(chat_id: int, text: str, msg: dict):
        captured["command"] = {"chat_id": chat_id, "text": text, "signal": dict(msg.get("_ea_route_signal") or {})}

    async def _on_intent(chat_id: int, msg: dict):
        captured["intent"] = {"chat_id": chat_id, "signal": dict(msg.get("_ea_route_signal") or {})}

    async def _run() -> None:
        await route_update(
            {
                "message": {
                    "chat": {"id": 55},
                    "text": "Please rebook my flight and review https://example.com",
                }
            },
            on_callback=_on_callback,
            on_command=_on_command,
            on_intent=_on_intent,
        )
        await route_update(
            {"message": {"chat": {"id": 55}, "text": "/brief"}},
            on_callback=_on_callback,
            on_command=_on_command,
            on_intent=_on_intent,
        )

    asyncio.run(_run())

    intent = dict(captured.get("intent") or {})
    signal = dict(intent.get("signal") or {})
    assert int(intent.get("chat_id") or 0) == 55
    assert signal.get("surface_type") == "text"
    assert signal.get("has_url") is True
    assert signal.get("domain") == "travel"
    assert signal.get("task_type") == "travel_rescue"

    command = dict(captured.get("command") or {})
    cmd_signal = dict(command.get("signal") or {})
    assert cmd_signal.get("is_command") is True
    _pass("v1.22 route-signal router behavior")


if __name__ == "__main__":
    test_route_signal_router_wiring()
    test_route_signal_router_behavior()
