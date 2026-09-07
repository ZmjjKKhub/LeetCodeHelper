"""GET /api/progress."""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from leetcode_helper.models import Attempt, DurationBucket, Mark, PlanStatus
from leetcode_helper.seed.bundle import load_bundle
from leetcode_helper.seed.importer import import_bundle
from tests.conftest import TODAY, make_client, seed

REPO_ROOT = Path(__file__).resolve().parent.parent
SLIDING_WINDOW_TOPIC_DIR = REPO_ROOT / "data" / "topics" / "sliding-window"


def test_api_progress_fallback_mode_plan_is_null(engine):
    seed(engine, with_plan=False)
    response = make_client(engine).get("/api/progress")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()

    assert body["topic"] == {"code": "sliding-window", "name": "滑动窗口"}
    assert body["plan"] is None
    assert body["stats"]["total"] == 1
    assert len(body["sections"]) == 1
    section = body["sections"][0]
    assert section["section"] == "§2.2"
    assert section["total"] == 1
    assert section["done"] == 0
    assert section["problems"] == [
        {"lc_id": 209, "title": "长度最小的子数组", "state": "todo", "outcome": None}
    ]


def test_api_progress_plan_mode_reports_day_position_and_today_state(engine):
    seed(engine, with_plan=True)
    response = make_client(engine).get("/api/progress")

    assert response.status_code == 200
    body = response.json()

    assert body["plan"] == {
        "day_index": 1,
        "total_days": 1,
        "phase": "阶段一",
        "planned_date": "2026-09-01",
    }
    section = body["sections"][0]
    assert section["problems"][0]["state"] == "today"


def test_api_progress_done_item_carries_outcome(engine):
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=TODAY,
                duration_bucket=DurationBucket.over,
                time_limit_sec=1200,
                submit_count=4,
                mark=Mark.B,
            )
        )
        session.commit()

    body = make_client(engine).get("/api/progress").json()
    problem = body["sections"][0]["problems"][0]
    assert problem["state"] == "done"
    assert problem["outcome"] == "over"
    assert body["stats"]["attempted"] == 1


def test_api_progress_uses_date_query_param(engine):
    seed(engine, with_plan=True)
    other_day = date(2026, 9, 2)
    response = make_client(engine, today=other_day).get(
        "/api/progress", params={"date": "2026-09-01"}
    )
    assert response.status_code == 200
    body = response.json()
    assert body["plan"]["day_index"] == 1


def test_api_progress_no_active_topic_is_503_json(engine):
    response = make_client(engine).get("/api/progress")
    assert response.status_code == 503
    body = response.json()
    assert "detail" in body
    assert "seed" in body["detail"]


def _make_seeded_sliding_window_engine():
    engine = create_engine(
        "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
    )
    SQLModel.metadata.create_all(engine)
    bundle = load_bundle(SLIDING_WINDOW_TOPIC_DIR)
    with Session(engine) as session:
        import_bundle(session, bundle)
    return engine


def test_api_progress_against_real_seed_data_reports_15_problems_across_two_sections():
    """The shipped data/topics/sliding-window catalogue: 15 problems total,
    §1.1 with 8 and §1.2 with 7 -- and today (inside the 5-day default plan,
    day 3) reports the right day position."""
    engine = _make_seeded_sliding_window_engine()

    # plan_default.yaml's start_date is 2026-08-31, day_index 3 -> 2026-09-02.
    response = make_client(engine, today=date(2026, 9, 2)).get("/api/progress")

    assert response.status_code == 200
    body = response.json()

    assert body["topic"]["code"] == "sliding-window"
    assert body["stats"]["total"] == 15
    assert [s["section"] for s in body["sections"]] == ["§1.1", "§1.2"]
    assert body["sections"][0]["total"] == 8
    assert body["sections"][1]["total"] == 7
    assert sum(s["total"] for s in body["sections"]) == 15

    assert body["plan"] is not None
    assert body["plan"]["day_index"] == 3
    assert body["plan"]["total_days"] == 5
