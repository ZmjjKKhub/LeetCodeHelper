from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine, select

from leetcode_helper.models import Attempt, Difficulty, DurationBucket, Mark, Problem, Topic
from leetcode_helper.web.app_factory import create_app

CONFIG_JSON = (
    '{"code": "sliding-window", "name": "sw", '
    '"time_limits": {"easy": 480, "medium": 1200, "hard": 2100}, "card_fields": []}'
)


@pytest.fixture
def engine():
    # StaticPool is required (not just check_same_thread=False): TestClient
    # dispatches requests on a different thread than the test body, and the
    # default SingletonThreadPool for sqlite ":memory:" hands each thread its
    # own separate in-memory database -- the seeded rows would be invisible
    # to the request. StaticPool shares one connection across threads. (Same
    # bug the Task 9 plan fixture had; the Task 10 plan text has it too.)
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        topic = Topic(code="sliding-window", name="滑动窗口", config_json=CONFIG_JSON)
        session.add(topic)
        session.commit()
        session.refresh(topic)
        session.add(
            Problem(
                topic_id=topic.id,
                lc_id=209,
                title="长度最小的子数组",
                url="https://leetcode.cn/problems/minimum-size-subarray-sum/",
                difficulty=Difficulty.medium,
                section="§2.2",
                section_name="越长越合法",
                default_template="C",
            )
        )
        session.commit()
    return engine


@pytest.fixture
def client(engine):
    return TestClient(create_app(engine=engine, today_provider=lambda: date(2026, 9, 1)))


def test_post_attempt_persists_and_returns_updated_row(client, engine):
    response = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "over",
            "mark": "C",
            "submit_count": "3",
            "used_template": "C",
        },
    )

    assert response.status_code == 200
    assert 'id="problem-1"' in response.text
    assert "已录入" in response.text
    assert "<form" not in response.text

    with Session(engine) as session:
        attempt = session.exec(select(Attempt)).one()
        assert attempt.mark is Mark.C
        assert attempt.duration_bucket is DurationBucket.over
        assert attempt.submit_count == 3
        assert attempt.time_limit_sec == 1200
        assert attempt.used_template == "C"


def test_post_attempt_treats_empty_template_as_none(client, engine):
    client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
            "used_template": "",
        },
    )
    with Session(engine) as session:
        assert session.exec(select(Attempt)).one().used_template is None


def test_post_attempt_rejects_bad_submit_count(client):
    response = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "0",
        },
    )
    assert response.status_code == 422


def test_post_attempt_rejects_bad_submit_count_returns_html_not_json(client, engine):
    # HTTPException's default body is application/json -- HTMX would either
    # swap a raw JSON blob into the page or (depending on config) swap
    # nothing at all, leaving the user with no feedback. The error body must
    # be an HTML fragment, scoped to the same row id the form targeted, so a
    # future front-end wire-up (see base.html's beforeSwap hook) can show it.
    response = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "0",
        },
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="problem-1"' in response.text
    assert not response.text.lstrip().startswith("{")

    # And nothing was persisted.
    with Session(engine) as session:
        assert session.exec(select(Attempt)).all() == []


def test_post_attempt_bad_enum_value_is_html_422(client):
    # mark="Z" fails FastAPI/Pydantic's own enum coercion *before* the route
    # body ever runs -- this bypasses our try/except entirely and, unless a
    # validation-error handler is registered, falls back to FastAPI's default
    # JSON error body.
    response = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "Z",
            "submit_count": "1",
        },
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert not response.text.lstrip().startswith("{")


def test_post_attempt_unknown_problem_id_is_404_html(client):
    response = client.post(
        "/attempts",
        data={
            "problem_id": "999",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
        },
    )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="problem-999"' in response.text


def test_post_attempt_missing_duration_sec_field_is_fine(client):
    # The current form never submits duration_sec at all -- it must not be
    # required.
    response = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
        },
    )
    assert response.status_code == 200


def test_double_submission_same_day_keeps_latest_attempt_and_no_crash(client, engine):
    first = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "over",
            "mark": "C",
            "submit_count": "2",
        },
    )
    second = client.post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    # The re-rendered row after the second submission must reflect the
    # *second* attempt (mark=A, bucket=within), matching what
    # repositories/today.py's "latest wins" rule would show on a fresh
    # GET /today -- not the first attempt's mark=C/over.
    assert "A / within" in second.text
    assert "C / over" not in second.text

    with Session(engine) as session:
        attempts = session.exec(select(Attempt).order_by(Attempt.id)).all()
        assert len(attempts) == 2
        assert attempts[0].mark is Mark.C
        assert attempts[1].mark is Mark.A


def test_get_today_after_post_is_consistent_with_fallback_filtering(client):
    # This fixture has no active Plan/PlanDay, so GET /today runs in
    # "fallback" mode: repositories/today.py's get_today_view excludes any
    # problem with an existing Attempt entirely (it's not "still to do"
    # under the fallback listing), rather than showing it as done inline.
    # POST /attempts must not fight that -- after recording an attempt the
    # only problem in this fixture disappears from the todo list, same as if
    # the attempt had been seeded directly and the page loaded fresh.
    post_response = client.post(
        "/attempts",
        data={"problem_id": "1", "duration_bucket": "within", "mark": "A", "submit_count": "1"},
    )
    assert post_response.status_code == 200
    assert "已录入" in post_response.text

    body = client.get("/today").text
    assert "没有待做的题了" in body
