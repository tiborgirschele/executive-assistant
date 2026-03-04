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


def test_teable_sync_runtime_contracts() -> None:
    import types

    if "httpx" not in sys.modules:
        fake_httpx = types.ModuleType("httpx")

        class _AsyncClient:
            def __init__(self, *args, **kwargs) -> None:
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return None

        fake_httpx.AsyncClient = _AsyncClient
        sys.modules["httpx"] = fake_httpx

    import app.integrations.teable.sync_worker as sw

    assert sw.DEFAULT_TEABLE_API_BASE_URL == "https://app.teable.ai/api"
    assert sw.resolve_teable_base_url("https://app.teable.io/api") == "https://app.teable.ai/api"
    assert sw.resolve_teable_base_url("https://app.teable.ai") == "https://app.teable.ai/api"

    ok_fields = sw.build_memory_record_fields("Household rule", "No school pickups after 18:00.")
    assert isinstance(ok_fields, dict)
    for key in ("Concept", "Core Fact", "Source", "Confidence", "Last Verified", "Sensitivity", "Sharing Policy", "Reviewer"):
        assert key in ok_fields

    blocked = sw.build_memory_record_fields(
        "raw_dump",
        '{"role":"assistant","content":"traceback ... tool_call ..."}',
    )
    assert blocked is None
    _pass("v1.20 teable sync runtime contracts")


def test_teable_compose_and_docs_alignment() -> None:
    compose = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    docs = (ROOT / "docs/EA_OS_Teable_Memory_Model.md").read_text(encoding="utf-8")
    assert "ea-teable-sync:" in compose
    assert "- ./attachments:/attachments:rw" in compose
    assert "curated memory projection layer" in docs
    assert "Runtime-local first" in docs
    _pass("v1.20 teable compose/docs alignment")


if __name__ == "__main__":
    test_teable_sync_runtime_contracts()
    test_teable_compose_and_docs_alignment()
