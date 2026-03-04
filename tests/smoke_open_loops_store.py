from __future__ import annotations

import json
import tempfile
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
EA_ROOT = ROOT / "ea"
if str(EA_ROOT) not in sys.path:
    sys.path.insert(0, str(EA_ROOT))


def test_open_loops_store_contract() -> None:
    import app.open_loops as store
    from app.open_loops import OpenLoops

    src = (EA_ROOT / "app/open_loops.py").read_text(encoding="utf-8")
    assert "_LOCK = threading.RLock()" in src
    assert "with cls._LOCK:" in src
    assert "os.replace(tmp, LOOPS_FILE)" in src
    assert "encoding=\"utf-8\"" in src

    with tempfile.TemporaryDirectory(prefix="ea_open_loops_") as td:
        old_path = store.LOOPS_FILE
        try:
            store.LOOPS_FILE = str(Path(td) / "open_loops.json")
            pid = OpenLoops.add_payment("t1", "Invoice", "12.34", "AT001", status="ready")
            assert pid
            cid = OpenLoops.add_calendar("t1", "preview", [{"title": "A", "start": "2026-03-04T10:00:00+01:00"}])
            assert cid
            OpenLoops.add_shopping("t1", "cat food")
            OpenLoops.remove_payment("t1", pid)
            cal = OpenLoops.get_calendar("t1", cid)
            assert cal and cal.get("id") == cid, cal

            data = json.loads(Path(store.LOOPS_FILE).read_text(encoding="utf-8"))
            assert "t1" in data
        finally:
            store.LOOPS_FILE = old_path

    print("[SMOKE][HOST][PASS] open loops store contract", flush=True)


if __name__ == "__main__":
    test_open_loops_store_contract()

