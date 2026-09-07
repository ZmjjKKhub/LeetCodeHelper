"""POST /api/attempts."""

from __future__ import annotations

from sqlmodel import Session, select

from leetcode_helper.models import Attempt, DurationBucket, Mark
from tests.conftest import CORRUPT_CONFIG_JSON, make_client, seed


def test_post_api_attempts_creates_and_returns_item_shape(client, engine):
    response = client.post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "unsolved", "submit_count": 3, "used_template": "C"},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert body["is_done"] is True
    assert body["time_limit_sec"] == 1200
    assert body["attempt"] == {"outcome": "unsolved", "submit_count": 3, "used_template": "C"}
    assert body["problem"]["lc_id"] == 209

    with Session(engine) as session:
        attempt = session.exec(select(Attempt)).one()
        assert attempt.mark is Mark.C
        assert attempt.duration_bucket is DurationBucket.unsolved
        assert attempt.submit_count == 3
        assert attempt.used_template == "C"


def test_post_api_attempts_treats_missing_used_template_as_none(client, engine):
    response = client.post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "within_solid", "submit_count": 1},
    )
    assert response.status_code == 200
    assert response.json()["attempt"]["used_template"] is None
    with Session(engine) as session:
        assert session.exec(select(Attempt)).one().used_template is None


def test_post_api_attempts_corrects_in_place_no_second_row(client, engine):
    # C1: re-posting for the same problem/day must update the existing
    # Attempt row, not insert a second one -- exactly the "correcting must
    # never insert a second row" rule the HTML form's 修改 control depends on.
    first = client.post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "unsolved", "submit_count": 2},
    )
    second = client.post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "within_solid", "submit_count": 1, "used_template": "A"},
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["attempt"] == {
        "outcome": "within_solid",
        "submit_count": 1,
        "used_template": "A",
    }

    with Session(engine) as session:
        attempts = session.exec(select(Attempt).order_by(Attempt.id)).all()
        assert len(attempts) == 1
        assert attempts[0].mark is Mark.A
        assert attempts[0].duration_bucket is DurationBucket.within
        assert attempts[0].submit_count == 1
        assert attempts[0].used_template == "A"


def test_post_api_attempts_unknown_problem_id_is_404_json(client):
    response = client.post(
        "/api/attempts",
        json={"problem_id": 9999, "outcome": "within_solid", "submit_count": 1},
    )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()
    assert "detail" in body
    assert not response.text.lstrip().startswith("<")


def test_post_api_attempts_bad_outcome_enum_value_is_422_json(client):
    response = client.post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "not_a_real_option", "submit_count": 1},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert not response.text.lstrip().startswith("<")
    # FastAPI's own default request-validation error body.
    assert "detail" in response.json()


def test_post_api_attempts_bad_submit_count_is_422_json(client, engine):
    response = client.post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "within_solid", "submit_count": 0},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")
    assert not response.text.lstrip().startswith("<")
    assert "submit_count" in response.json()["detail"]

    # Nothing persisted for a rejected submit_count.
    with Session(engine) as session:
        assert session.exec(select(Attempt)).all() == []


def test_post_api_attempts_corrupt_topic_config_is_422_json_not_500(engine):
    # Mirrors test_web_attempt_post.py::test_post_attempt_corrupt_topic_config_is_422_not_500 --
    # a corrupt topic.config_json raises a TopicConfigError (a ValueError
    # subclass) inside record_attempt, which the route must turn into a 422,
    # not an unhandled 500.
    seed(engine, with_plan=False, config_json=CORRUPT_CONFIG_JSON)
    response = make_client(engine).post(
        "/api/attempts",
        json={"problem_id": 1, "outcome": "within_solid", "submit_count": 1},
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("application/json")

    with Session(engine) as session:
        assert session.exec(select(Attempt)).all() == []
