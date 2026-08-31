from sqlmodel import Session, select

from leetcode_helper.models import Attempt, DurationBucket, Mark
from tests.conftest import CORRUPT_CONFIG_JSON, make_client, seed


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
    # be an HTML fragment, scoped to the same row id the form targeted, so
    # base.html's beforeSwap hook can show it.
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


def test_post_attempt_validation_error_row_is_reusable(client):
    # I5: the row the server sends back after a validation failure must not
    # be a dead end -- the user should be able to fix the field and retry
    # immediately, not be forced into a full page reload. record_attempt's
    # own ValueError path (submit_count/duration_sec validation) goes through
    # routes/today.py's _error_row_response, which re-renders the full
    # partials/_problem_row.html (form included), not a bare message.
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
    assert "<form" in response.text
    assert 'name="mark" value="A"' in response.text
    assert 'name="duration_bucket"' in response.text


def test_post_attempt_bad_enum_value_is_html_422(client):
    # mark="Z" fails FastAPI/Pydantic's own enum coercion *before* the route
    # body ever runs -- this bypasses our try/except entirely and is handled
    # by app_factory's RequestValidationError handler instead.
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
    # The whole point of the form-re-read in the RequestValidationError
    # handler is to recover problem_id and re-render *this* row -- assert
    # that actually happened, not just that "some HTML" came back.
    assert 'id="problem-1"' in response.text
    assert "<form" in response.text


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


def test_post_attempt_missing_problem_id_is_422_html_not_json(client):
    response = client.post(
        "/attempts",
        data={
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
        },
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert not response.text.lstrip().startswith("{")


def test_post_attempt_non_numeric_problem_id_does_not_inject_html(client):
    # C2 probe: problem_id read raw out of the form (because Pydantic's own
    # int coercion already failed) used to be f-string-interpolated straight
    # into the response body, bypassing Jinja autoescape. A crafted value
    # used to come back live as an executable <script> tag.
    payload = '"><script>alert(1)</script>'
    response = client.post(
        "/attempts",
        data={
            "problem_id": payload,
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
        },
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert "<script>alert(1)</script>" not in response.text
    assert "problem-\"><script>" not in response.text


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


def test_post_attempt_corrupt_topic_config_is_422_not_500(engine):
    # C3: TopicConfigError subclasses ValueError, so a corrupt
    # topic.config_json raises inside record_attempt, gets caught by the
    # route's `except ValueError`, and then _error_row_response used to
    # re-parse the *same* corrupt config while building the error row --
    # raising a second time, uncaught, as an unhandled 500.
    seed(engine, with_plan=False, config_json=CORRUPT_CONFIG_JSON)
    response = make_client(engine).post(
        "/attempts",
        data={
            "problem_id": "1",
            "duration_bucket": "within",
            "mark": "A",
            "submit_count": "1",
        },
    )
    assert response.status_code == 422
    assert response.headers["content-type"].startswith("text/html")
    assert 'id="problem-1"' in response.text

    with Session(engine) as session:
        assert session.exec(select(Attempt)).all() == []


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


