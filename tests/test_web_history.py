from __future__ import annotations

from datetime import date

from sqlmodel import Session

from leetcode_helper.models import Attempt, DurationBucket, Mark
from leetcode_helper.web.routes import history as history_routes

from .conftest import make_client, seed


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


def test_history_page_lists_attempts(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id)
    client = make_client(engine)

    body = client.get("/history").text

    assert "2026-08-30" in body
    assert "长度最小的子数组" in body
    assert "没做出来" in body
    assert "C" in body


def test_history_page_shows_empty_state(engine):
    # A topic and problem exist, but no attempt has ever been recorded --
    # this must render the empty state, distinct from the "no topic at
    # all" 503 case (already covered by NoActiveTopic tests elsewhere).
    seed(engine, with_plan=False)
    client = make_client(engine)

    assert "还没有任何做题记录" in client.get("/history").text


def test_history_page_orders_newest_first(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 20), mark=Mark.A)
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 25), mark=Mark.B)
    client = make_client(engine)

    body = client.get("/history").text
    assert body.index("2026-08-25") < body.index("2026-08-20")


def test_history_page_computes_first_try_ac(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(
        engine,
        problem_id,
        duration_bucket=DurationBucket.within,
        submit_count=1,
        mark=Mark.A,
    )
    client = make_client(engine)

    body = client.get("/history").text
    assert "是" in body


def test_history_page_shows_truncation_notice_when_limit_hit(engine, monkeypatch):
    monkeypatch.setattr(history_routes, "HISTORY_LIMIT", 1)
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 20))
    _add_attempt(engine, problem_id, attempt_date=date(2026, 8, 21))
    client = make_client(engine)

    body = client.get("/history").text
    assert "共 1 条记录" in body
    assert "仅显示最近 1 条" in body
    # Only the newest of the two attempts should actually be rendered.
    assert "2026-08-21" in body
    assert "2026-08-20" not in body


def test_history_page_no_truncation_notice_under_limit(engine):
    _, problem_id = seed(engine, with_plan=False)
    _add_attempt(engine, problem_id)
    client = make_client(engine)

    body = client.get("/history").text
    assert "共 1 条记录" in body
    assert "仅显示最近" not in body


def test_history_page_uses_repository_not_raw_select(engine):
    # Sanity guard against the plan's regression risk: the route must go
    # through active_topic()/list_history() and never issue its own
    # select() -- verified indirectly by asserting the route module has no
    # sqlmodel `select` imported into its namespace.
    import leetcode_helper.web.routes.history as mod

    assert not hasattr(mod, "select")


def test_history_page_no_active_topic_returns_503(engine):
    # No Topic seeded at all -- must be the existing NoActiveTopic 503
    # handler, distinct from the "topic exists, zero attempts" empty state.
    client = make_client(engine)
    resp = client.get("/history")
    assert resp.status_code == 503
