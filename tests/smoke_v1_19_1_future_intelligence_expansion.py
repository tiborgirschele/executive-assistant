from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "ea"))

from app.intelligence.critical_lane import build_critical_actions  # noqa: E402
from app.intelligence.dossiers import (  # noqa: E402
    build_finance_commitment_dossier,
    build_project_dossier,
)
from app.intelligence.future_situations import build_future_situations  # noqa: E402
from app.intelligence.profile import build_profile_context  # noqa: E402
from app.intelligence.readiness import build_readiness_dossier  # noqa: E402


def _pass(name: str) -> None:
    print(f"[SMOKE][HOST][PASS] {name}")


def test_v1191_module_contracts() -> None:
    src = (ROOT / "ea/app/intelligence/dossiers.py").read_text(encoding="utf-8")
    assert "def build_project_dossier(" in src
    assert "def build_finance_commitment_dossier(" in src
    future_src = (ROOT / "ea/app/intelligence/future_situations.py").read_text(encoding="utf-8")
    assert "meeting_prep_window" in future_src
    assert "deadline_window" in future_src
    _pass("v1.19.1 module contracts")


def test_v1191_behavior_contracts() -> None:
    future_start = (datetime.now(timezone.utc) + timedelta(hours=18)).isoformat()
    profile = build_profile_context(tenant="ea_bot", person_id="tibor")

    project_dossier = build_project_dossier(
        mails=[
            {
                "subject": "Project launch blocker needs decision",
                "snippet": "Deadline moved. Action required before tomorrow meeting.",
            }
        ],
        calendar_events=[
            {
                "summary": "Client project milestone review",
                "start": {"dateTime": future_start},
                "location": "Office",
            }
        ],
    )
    finance_dossier = build_finance_commitment_dossier(
        mails=[
            {
                "subject": "Final notice: invoice due tomorrow EUR 4,500",
                "snippet": "Payment overdue warning",
            }
        ],
        calendar_events=[
            {
                "summary": "Insurance payment due",
                "start": {"dateTime": future_start},
                "location": "",
            }
        ],
    )

    situations = build_future_situations(
        profile=profile,
        dossiers=[project_dossier, finance_dossier],
        calendar_events=[],
        horizon_hours=96,
    )
    kinds = {s.kind for s in situations}
    assert "meeting_prep_window" in kinds, kinds
    assert "deadline_window" in kinds, kinds

    readiness = build_readiness_dossier(
        profile=profile,
        dossiers=[project_dossier, finance_dossier],
        future_situations=situations,
    )
    assert readiness.status in {"watch", "critical"}, readiness
    assert len(readiness.suggested_actions) >= 1, readiness

    critical = build_critical_actions(profile, [project_dossier, finance_dossier])
    assert len(critical.actions) >= 1, critical
    assert critical.decision_window_score > 0, critical
    _pass("v1.19.1 behavior contracts")


if __name__ == "__main__":
    test_v1191_module_contracts()
    test_v1191_behavior_contracts()
