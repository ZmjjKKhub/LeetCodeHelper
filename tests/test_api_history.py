"""GET /api/history."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session

from leetcode_helper.models import Attempt, DurationBucket, Mark
from tests.conftest import make_client, seed


def _add_attempt(engine, problem_id: int, **overrides) -> None:
    defaults = dict(
        problem_id=problem_id,
        attempt_date=date(2026, 8, 30),
        duration_bucket=DurationBucket.unsolved,
        time_limit_sec=1200,
        submit_count=5,
        mark=Mark.C,
        used_template="C",
    )
    defaults.update(overrides)
    with Session(engine) as session:
        session.add(Attempt(**defaults))
        session.commit()


def test_api_history_happy_path_shape(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id)
    response = make_client(engine).get("/api/history")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["limit"] == 500
    assert body["truncated"] is False
    assert len(body["rows"]) == 1

    row = body["rows"][0]
    assert row["date"] == "2026-08-30"
    assert row["problem"]["lc_id"] == 209
    assert row["duration_bucket"] == "unsolved"
    assert row["mark"] == "C"
    assert row["submit_count"] == 5
    assert row["used_template"] == "C"
    assert row["first_try_ac"] is False


def test_api_history_first_try_ac_true_case(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id, duration_bucket=DurationBucket.within, submit_count=1, mark=Mark.A)
    body = make_client(engine).get("/api/history").json()
    assert body["rows"][0]["first_try_ac"] is True


def test_api_history_orders_newest_first(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 20), mark=Mark.A)
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 25), mark=Mark.B)
    body = make_client(engine).get("/api/history").json()
    assert [row["date"] for row in body["rows"]] == ["2026-08-25", "2026-08-20"]


def test_api_history_respects_limit_query_param(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 20))
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 21))
    response = make_client(engine).get("/api/history", params={"limit": 1})
    body = response.json()
    assert body["limit"] == 1
    assert body["truncated"] is True
    assert len(body["rows"]) == 1
    assert body["rows"][0]["date"] == "2026-08-21"


def test_api_history_empty_state(engine):
    seed(engine, with_plan=False)
    body = make_client(engine).get("/api/history").json()
    assert body["rows"] == []
    assert body["truncated"] is False


def test_api_history_no_active_topic_is_503_json(engine):
    response = make_client(engine).get("/api/history")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert "detail" in response.json()


def test_api_history_shows_one_row_per_corrected_attempt_not_two(engine):
    _, problem_id = seed(engine, with_plan=False)
    client = make_client(engine)
    client.post(
        "/api/attempts",
        json={"problem_id": problem_id, "outcome": "over", "submit_count": 1},
    )
    client.post(
        "/api/attempts",
        json={"problem_id": problem_id, "outcome": "within_solid", "submit_count": 1},
    )
    body = client.get("/api/history").json()
    assert len(body["rows"]) == 1
    assert body["rows"][0]["mark"] == "A"
