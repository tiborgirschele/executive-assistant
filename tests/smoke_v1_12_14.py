from __future__ import annotations

import ast
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLL = ROOT / "ea/app/poll_listener.py"
REPAIR = ROOT / "ea/app/repair_registry.py"
GUARD = ROOT / "ea/app/render_guard.py"

poll_src = POLL.read_text(encoding="utf-8")
ast.parse(poll_src)
assert "MarkupGo rendering failed" not in poll_src
assert "from app.render_guard import" in poll_src
assert "markupgo_breaker_open" in poll_src
assert "EA v1.12.11 renderer repair bootstrap" not in poll_src
print("[SMOKE][HOST][PASS] poll_listener real-path patch + old bootstrap removal")

spec_guard = importlib.util.spec_from_file_location("ea_render_guard_host", GUARD)
render_guard = importlib.util.module_from_spec(spec_guard)
spec_guard.loader.exec_module(render_guard)
assert render_guard.classify_markupgo_error("MarkupGo API HTTP 400. source/data/id: Invalid template id") == "invalid_template_id"
assert render_guard.classify_markupgo_error("renderer unavailable due to timeout") == "renderer_unavailable"
render_guard.open_markupgo_breaker("invalid_template_id", skill="markupgo", location="host_smoke")
assert render_guard.markupgo_breaker_open() is True
print("[SMOKE][HOST][PASS] render_guard classification + breaker")

spec_repair = importlib.util.spec_from_file_location("ea_repair_registry_host", REPAIR)
repair_registry = importlib.util.module_from_spec(spec_repair)
spec_repair.loader.exec_module(repair_registry)
for key in ("renderer_template_swap", "renderer_text_only", "breaker_open_optional_skill"):
    assert key in repair_registry.REPAIR_RECIPES
print("[SMOKE][HOST][PASS] recipe registry keys")
