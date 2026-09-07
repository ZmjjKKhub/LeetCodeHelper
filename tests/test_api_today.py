"""GET /api/today."""

from __future__ import annotations

from datetime import date

from sqlmodel import Session

from leetcode_helper.models import Attempt, AttemptKind, DurationBucket, Mark, Topic
from tests.conftest import TODAY, make_client, seed


def test_api_today_plan_mode_shape(engine):
    seed(engine, with_plan=True)
    response = make_client(engine).get("/api/today")

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()

    assert body["topic"] == {"code": "sliding-window", "name": "滑动窗口"}
    assert body["date"] == "2026-09-01"
    assert body["is_fallback"] is False
    assert body["phase"] == "阶段一"
    assert body["theme"] == "定长窗口三步走"
    assert len(body["items"]) == 1

    item = body["items"][0]
    assert item["problem"]["lc_id"] == 209
    assert item["problem"]["title"] == "长度最小的子数组"
    assert item["problem"]["section"] == "§2.2"
    assert item["problem"]["section_name"] == "越长越合法"
    assert item["problem"]["difficulty"] == "medium"
    assert item["problem"]["is_starred"] is False
    assert item["problem"]["is_optional"] is False
    assert item["time_limit_sec"] == 1200
    assert item["is_done"] is False
    assert item["derived_template"] == "C"
    assert item["attempt"] is None


def test_api_today_fallback_mode_items_carry_section_for_grouping(engine):
    seed(engine, with_plan=False)
    response = make_client(engine).get("/api/today")

    assert response.status_code == 200
    body = response.json()
    assert body["is_fallback"] is True
    # Fallback mode has no PlanDay -- phase/theme are blank, not omitted.
    assert body["phase"] == ""
    assert body["theme"] == ""
    # Items are flat (not nested by section); each item carries its own
    # section so the frontend can group client-side.
    assert len(body["items"]) == 1
    assert body["items"][0]["problem"]["section"] == "§2.2"


def test_api_today_done_item_carries_recorded_outcome(engine):
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=TODAY,
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.over,
                time_limit_sec=1200,
                submit_count=4,
                mark=Mark.B,
                used_template="A",
            )
        )
        session.commit()

    body = make_client(engine).get("/api/today").json()
    item = body["items"][0]
    assert item["is_done"] is True
    assert item["attempt"] == {
        "outcome": "over",
        "submit_count": 4,
        "used_template": "A",
    }
    # derived_template (Problem.default_template = "C") differs from what
    # was actually recorded ("A") -- both must be visible so the frontend
    # can show "原本预期 C".
    assert item["derived_template"] == "C"


def test_api_today_done_item_reports_snapshotted_time_limit_not_fresh_lookup(engine):
    # C1/snapshot rule: a done row must show the limit the attempt was
    # actually judged against, not a fresh lookup from the topic's *current*
    # config -- which may have changed since the attempt was recorded.
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=TODAY,
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.within,
                time_limit_sec=999,  # deliberately not the config's 1200
                submit_count=1,
                mark=Mark.A,
            )
        )
        session.commit()
        # Change the topic's live config after the attempt was recorded.
        topic = session.get(Topic, topic_id)
        topic.config_json = (
            '{"code": "sliding-window", "name": "滑动窗口", '
            '"time_limits": {"easy": 480, "medium": 7777, "hard": 2100}, "card_fields": []}'
        )
        session.add(topic)
        session.commit()

    body = make_client(engine).get("/api/today").json()
    assert body["items"][0]["time_limit_sec"] == 999


def test_api_today_uses_date_query_param(engine):
    seed(engine, with_plan=True)
    other_day = date(2026, 9, 2)
    response = make_client(engine, today=other_day).get("/api/today", params={"date": "2026-09-01"})
    assert response.status_code == 200
    body = response.json()
    # Plan day is scheduled for TODAY (2026-09-01), not the injected
    # today_provider's 2026-09-02 -- the ?date= override took effect.
    assert body["date"] == "2026-09-01"
    assert body["is_fallback"] is False
    assert len(body["items"]) == 1


def test_api_today_no_active_topic_is_503_json(engine):
    response = make_client(engine).get("/api/today")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "detail" in body
    assert "seed" in body["detail"]


def test_api_today_unrelated_keyerror_is_500_not_disguised_as_no_active_topic(engine, monkeypatch):
    # Ported from the deleted tests/test_web_today.py -- C1: the
    # NoActiveTopic exception handler in app_factory.py is registered on
    # NoActiveTopic specifically, *not* the bare LookupError it subclasses.
    # LookupError is also the base class of KeyError and IndexError, so
    # catching it broadly would silently relabel an unrelated internal bug
    # (e.g. a raw dict/list subscript error anywhere in the request) as "you
    # forgot to seed" (503) with its traceback destroyed, instead of
    # surfacing as the 500 it actually is.
    seed(engine, with_plan=True)

    import leetcode_helper.api.routes.today as today_api_routes

    def boom(*args, **kwargs):
        raise KeyError("some unrelated bug")

    monkeypatch.setattr(today_api_routes, "get_today_view", boom)

    response = make_client(engine, raise_server_exceptions=False).get("/api/today")
    assert response.status_code == 500
    assert response.status_code != 503
