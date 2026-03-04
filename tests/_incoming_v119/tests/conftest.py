
import os
import sys
from pathlib import Path
import pytest

def _candidate_roots():
    env = os.environ.get("EA_REPO_ROOT")
    if env:
        yield Path(env)
    here = Path(__file__).resolve()
    for p in [here.parent.parent.parent, here.parent.parent, Path.cwd()]:
        yield p

def _bootstrap_repo_path():
    for root in _candidate_roots():
        ea = root / "ea"
        if ea.exists():
            if str(ea) not in sys.path:
                sys.path.insert(0, str(ea))
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return root
    return None

REPO_ROOT = _bootstrap_repo_path()

@pytest.fixture(scope="session")
def repo_root():
    return REPO_ROOT

@pytest.fixture()
def sample_trip_inputs():
    mails = [
        {
            "subject": "Holiday booking confirmation - EUR 15,000",
            "from": "travel@example.com",
            "snippet": "Flight booking with layover in Tel Aviv. Rebooking terms attached.",
        }
    ]
    calendar_events = [
        {
            "summary": "Flight to Zurich",
            "location": "Vienna Airport; Tel Aviv Airport; Zurich, Switzerland",
            "start": {"dateTime": "2026-03-05T08:00:00+00:00"},
            "end": {"dateTime": "2026-03-05T18:00:00+00:00"},
            "_calendar": "primary",
        }
    ]
    return mails, calendar_events
