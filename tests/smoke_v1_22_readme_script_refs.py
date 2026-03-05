from __future__ import annotations

import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parents[1]


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_readme_script_refs_exist() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    refs = sorted(
        {
            str(match.group(1) or "").strip()
            for match in re.finditer(r"(scripts/[A-Za-z0-9_.-]+\.sh)", readme)
            if str(match.group(1) or "").strip()
        }
    )
    assert refs, "expected at least one scripts/*.sh reference in README"
    missing = [ref for ref in refs if not (ROOT / ref).exists()]
    assert not missing, f"README references missing scripts: {missing}"
    _pass("v1.22 readme script refs exist")


if __name__ == "__main__":
    test_readme_script_refs_exist()
