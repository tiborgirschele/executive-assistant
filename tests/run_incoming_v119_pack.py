from __future__ import annotations

import importlib.util
import inspect
import sys
import types
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EA_DIR = ROOT / "ea"
PACK_ROOT = ROOT / "tests/_incoming_v119"
PACK_TESTS = PACK_ROOT / "tests"


class _MiniMonkeyPatch:
    def __init__(self) -> None:
        self._setattrs: list[tuple[object, str, object, bool]] = []

    def setattr(self, obj: object, name: str, value: object) -> None:
        existed = hasattr(obj, name)
        old = getattr(obj, name, None)
        self._setattrs.append((obj, name, old, existed))
        setattr(obj, name, value)

    def undo(self) -> None:
        while self._setattrs:
            obj, name, old, existed = self._setattrs.pop()
            if existed:
                setattr(obj, name, old)
            else:
                try:
                    delattr(obj, name)
                except Exception:
                    pass


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _install_pytest_stub() -> None:
    # Host gates intentionally avoid requiring pytest in base image.
    if "pytest" in sys.modules:
        return

    pytest_mod = types.ModuleType("pytest")

    def fixture(*args, **kwargs):
        if len(args) == 1 and callable(args[0]) and not kwargs:
            return args[0]

        def decorator(fn):
            return fn

        return decorator

    class _Raises:
        def __init__(self, expected_exception: type[BaseException]) -> None:
            self._expected_exception = expected_exception

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb) -> bool:
            if exc_type is None:
                raise AssertionError(
                    f"Expected exception {self._expected_exception.__name__} was not raised"
                )
            if not issubclass(exc_type, self._expected_exception):
                raise AssertionError(
                    f"Expected {self._expected_exception.__name__}, got {exc_type.__name__}"
                )
            return True

    def raises(expected_exception: type[BaseException]):
        return _Raises(expected_exception)

    pytest_mod.fixture = fixture
    pytest_mod.raises = raises
    sys.modules["pytest"] = pytest_mod


def _install_optional_dep_stubs() -> None:
    # Telegram legacy bridge imports httpx at module import time.
    if "httpx" not in sys.modules:
        httpx_mod = types.ModuleType("httpx")

        class _DummyResponse:
            text = ""
            content = b""

            def json(self):
                return {"ok": True, "result": {}}

        class _DummyAsyncClient:
            def __init__(self, *args, **kwargs):
                pass

            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                return _DummyResponse()

            async def get(self, *args, **kwargs):
                return _DummyResponse()

        httpx_mod.AsyncClient = _DummyAsyncClient
        sys.modules["httpx"] = httpx_mod

    # DB-heavy modules import psycopg2 even for host-only smoke checks.
    if "psycopg2" not in sys.modules:
        psycopg2_mod = types.ModuleType("psycopg2")
        pool_mod = types.ModuleType("psycopg2.pool")
        extras_mod = types.ModuleType("psycopg2.extras")

        class _SimpleConnectionPool:
            def __init__(self, *args, **kwargs):
                pass

            def getconn(self):
                raise RuntimeError("psycopg2 stub connection requested")

            def putconn(self, conn):
                return None

        class _DictCursor:
            pass

        class _RealDictCursor:
            pass

        pool_mod.SimpleConnectionPool = _SimpleConnectionPool
        extras_mod.DictCursor = _DictCursor
        extras_mod.RealDictCursor = _RealDictCursor

        psycopg2_mod.pool = pool_mod
        psycopg2_mod.extras = extras_mod

        sys.modules["psycopg2"] = psycopg2_mod
        sys.modules["psycopg2.pool"] = pool_mod
        sys.modules["psycopg2.extras"] = extras_mod


def _ensure_pack_conftest_alias() -> types.ModuleType:
    tests_pkg = sys.modules.get("tests")
    if tests_pkg is None:
        tests_pkg = types.ModuleType("tests")
        tests_pkg.__path__ = [str(PACK_TESTS)]  # type: ignore[attr-defined]
        sys.modules["tests"] = tests_pkg

    conftest_mod = _load_module("tests.conftest", PACK_TESTS / "conftest.py")
    sys.modules["tests.conftest"] = conftest_mod
    return conftest_mod


def _iter_test_modules() -> list[Path]:
    files: list[Path] = []
    files.extend(sorted(PACK_TESTS.glob("test_v1_12_*.py")))
    files.extend(sorted(PACK_TESTS.glob("test_v1_19_*.py")))
    return [p for p in files if p.exists()]


def run_pack() -> dict[str, int]:
    for p in (str(ROOT), str(EA_DIR)):
        if p not in sys.path:
            sys.path.insert(0, p)

    _install_pytest_stub()
    _install_optional_dep_stubs()
    conftest = _ensure_pack_conftest_alias()

    sample_trip_inputs = None
    if hasattr(conftest, "sample_trip_inputs"):
        sample_trip_inputs = conftest.sample_trip_inputs()

    total = 0
    failed = 0

    for path in _iter_test_modules():
        module_name = f"incoming_v119_{path.stem}"
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
                kwargs: dict[str, object] = {}

                if "sample_trip_inputs" in params:
                    kwargs["sample_trip_inputs"] = sample_trip_inputs
                if "repo_root" in params:
                    kwargs["repo_root"] = ROOT
                if "monkeypatch" in params:
                    kwargs["monkeypatch"] = patch

                unknown = [p for p in params if p not in {"sample_trip_inputs", "repo_root", "monkeypatch"}]
                if unknown:
                    raise TypeError(
                        f"Unsupported test signature for {test_fn.__module__}.{test_fn.__name__}: {params}"
                    )

                test_fn(**kwargs)
                print(f"[SMOKE][HOST][PASS] incoming-v119 {test_fn.__module__}.{test_fn.__name__}")
            except Exception as exc:
                failed += 1
                print(f"[SMOKE][HOST][FAIL] incoming-v119 {test_fn.__module__}.{test_fn.__name__}: {exc}")
            finally:
                patch.undo()

    total += 1
    if (ROOT / "scripts").exists():
        print("[SMOKE][HOST][PASS] incoming-v119 milestone release scaffold")
    else:
        failed += 1
        print("[SMOKE][HOST][FAIL] incoming-v119 milestone release scaffold: scripts/ missing")

    summary = {"total": total, "failed": failed}
    if failed:
        raise AssertionError(f"incoming-v119 contract pack failed: {summary}")
    print(f"[SMOKE][HOST][PASS] incoming-v119 contract pack ({total} tests)")
    return summary


if __name__ == "__main__":
    run_pack()
