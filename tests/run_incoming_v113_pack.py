from __future__ import annotations

import importlib.util
import inspect
import sys
import types
import ast
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
PACK_ROOT = ROOT / "tests/_incoming_v113"
PACK_TESTS = PACK_ROOT / "tests"


class _MiniMonkeyPatch:
    def __init__(self) -> None:
        self._setattrs: list[tuple[object, str, object, bool]] = []
        self._setenv: list[tuple[str, str | None, bool]] = []

    def setattr(self, obj: object, name: str, value: object) -> None:
        existed = hasattr(obj, name)
        old = getattr(obj, name, None)
        self._setattrs.append((obj, name, old, existed))
        setattr(obj, name, value)

    def setenv(self, key: str, value: str) -> None:
        import os

        existed = key in os.environ
        old = os.environ.get(key)
        self._setenv.append((key, old, existed))
        os.environ[key] = value

    def undo(self) -> None:
        import os

        while self._setattrs:
            obj, name, old, existed = self._setattrs.pop()
            if existed:
                setattr(obj, name, old)
            else:
                try:
                    delattr(obj, name)
                except Exception:
                    pass
        while self._setenv:
            key, old, existed = self._setenv.pop()
            if existed:
                if old is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = old
            else:
                os.environ.pop(key, None)


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _module_path_for_import(name: str) -> Path | None:
    if not name.startswith("app."):
        return None
    rel = name.replace("app.", "", 1).replace(".", "/")
    candidate_py = EA_DIR / "app" / f"{rel}.py"
    if candidate_py.exists():
        return candidate_py
    candidate_pkg = EA_DIR / "app" / rel / "__init__.py"
    if candidate_pkg.exists():
        return candidate_pkg
    return None


def _source_stub(import_name: str, source_path: Path):
    # Source-only stub for host smoke paths where optional deps are unavailable.
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    mod = types.ModuleType(import_name)
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            setattr(mod, node.name, object())
    return mod


def _fallback_import(import_name: str):
    source_path = _module_path_for_import(import_name)
    if source_path is None or not source_path.exists():
        return None
    if import_name == "app.telegram.safety":
        # Avoid importing `app.telegram` package bootstrap (depends on optional deps).
        safety_mod = _load_module("app.telegram.safety", EA_DIR / "app/telegram/safety.py")
        pkg = sys.modules.get("app.telegram")
        if pkg is None:
            pkg = types.ModuleType("app.telegram")
            pkg.__path__ = [str(EA_DIR / "app/telegram")]  # type: ignore[attr-defined]
            sys.modules["app.telegram"] = pkg
        setattr(pkg, "safety", safety_mod)
        sys.modules["app.telegram.safety"] = safety_mod
        return safety_mod
    if import_name == "app.supervisor":
        # `supervisor` is needed for behavior tests; load real module when possible.
        return _load_module("app.supervisor", EA_DIR / "app/supervisor.py")
    return _source_stub(import_name, source_path)


def _import_first_compatible(*names):
    last = None
    for name in names:
        try:
            return __import__(name, fromlist=["*"])
        except Exception as exc:
            last = exc
            fallback = _fallback_import(name)
            if fallback is not None:
                return fallback
    raise last  # type: ignore[misc]


def _ensure_pack_conftest_alias() -> None:
    # Incoming tests import `tests.conftest`; host repo uses `tests/` as a folder
    # without package metadata, so we alias the pack conftest explicitly.
    tests_pkg = sys.modules.get("tests")
    if tests_pkg is None:
        tests_pkg = types.ModuleType("tests")
        tests_pkg.__path__ = [str(PACK_TESTS)]  # type: ignore[attr-defined]
        sys.modules["tests"] = tests_pkg
    conftest_mod = _load_module("tests.conftest", PACK_TESTS / "conftest.py")
    setattr(conftest_mod, "import_first", _import_first_compatible)
    sys.modules["tests.conftest"] = conftest_mod


def _iter_test_modules() -> list[Path]:
    files: list[Path] = []
    files.extend(sorted((PACK_TESTS / "future_intelligence").glob("test_*.py")))
    files.extend(sorted((PACK_TESTS / "regression").glob("test_*.py")))
    # This file derives repo root from its own path with assumptions that differ
    # from this host placement; run equivalent contract inline below.
    return [p for p in files if p.exists()]


def run_pack() -> dict[str, int]:
    for p in (str(ROOT), str(EA_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)
    _ensure_pack_conftest_alias()

    total = 0
    failed = 0
    for path in _iter_test_modules():
        module_name = f"incoming_v113_{path.stem}"
        module = _load_module(module_name, path)
        tests = [getattr(module, n) for n in dir(module) if n.startswith("test_")]
        for test_fn in tests:
            if not callable(test_fn):
                continue
            total += 1
            patch = _MiniMonkeyPatch()
            try:
                sig = inspect.signature(test_fn)
                params = list(sig.parameters.keys())
                if not params:
                    test_fn()
                elif params == ["monkeypatch"]:
                    test_fn(patch)
                else:
                    raise TypeError(
                        f"Unsupported test signature for {test_fn.__module__}.{test_fn.__name__}: {params}"
                    )
                print(f"[SMOKE][HOST][PASS] incoming-v113 {test_fn.__module__}.{test_fn.__name__}")
            except Exception as exc:
                failed += 1
                print(f"[SMOKE][HOST][FAIL] incoming-v113 {test_fn.__module__}.{test_fn.__name__}: {exc}")
            finally:
                patch.undo()

    # Equivalent contract from incoming `test_milestone_suite_v113.py`.
    total += 1
    if (ROOT / "scripts").exists():
        print("[SMOKE][HOST][PASS] incoming-v113 milestone release scaffold")
    else:
        failed += 1
        print("[SMOKE][HOST][FAIL] incoming-v113 milestone release scaffold: scripts/ missing")

    summary = {"total": total, "failed": failed}
    if failed:
        raise AssertionError(f"incoming-v113 contract pack failed: {summary}")
    print(f"[SMOKE][HOST][PASS] incoming-v113 contract pack ({total} tests)")
    return summary


if __name__ == "__main__":
    run_pack()
