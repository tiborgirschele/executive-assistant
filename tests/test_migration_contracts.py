from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_schema_readme_lists_v0_5() -> None:
    text = (ROOT / "ea/schema/README.md").read_text()
    assert "20260305_v0_5_artifacts_kernel.sql" in text


def test_db_bootstrap_includes_v0_5() -> None:
    text = (ROOT / "scripts/db_bootstrap.sh").read_text()
    assert "20260305_v0_5_artifacts_kernel.sql" in text
