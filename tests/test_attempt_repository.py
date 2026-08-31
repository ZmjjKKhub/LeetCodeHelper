from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from leetcode_helper.models import (
    Attempt,
    Difficulty,
    DurationBucket,
    ItemStatus,
    Mark,
    Plan,
    PlanDay,
    PlanItem,
    PlanStatus,
    Problem,
    Topic,
)
from leetcode_helper.repositories.attempts import ProblemNotFound, list_history, record_attempt
from leetcode_helper.services.attempts import AttemptInput

CONFIG_JSON = (
    '{"code": "sliding-window", "name": "sw", '
    '"time_limits": {"easy": 480, "medium": 1200, "hard": 2100}, "card_fields": []}'
)


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def topic(session):
    topic = Topic(code="sliding-window", name="滑动窗口", config_json=CONFIG_JSON)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


@pytest.fixture
def problem(session, topic):
    problem = Problem(
        topic_id=topic.id,
        lc_id=209,
        title="长度最小的子数组",
        url="https://leetcode.cn/problems/minimum-size-subarray-sum/",
        difficulty=Difficulty.medium,
        section="§2.2",
        section_name="越长越合法",
    )
    session.add(problem)
    session.commit()
    session.refresh(problem)
    return problem


def _make_plan_item(session, topic_id, problem_id, planned_date, *, status=PlanStatus.active):
    plan = Plan(topic_id=topic_id, name="计划", start_date=planned_date, status=status)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    day = PlanDay(plan_id=plan.id, day_index=1, planned_date=planned_date)
    session.add(day)
    session.commit()
    session.refresh(day)
    item = PlanItem(plan_day_id=day.id, problem_id=problem_id)
    session.add(item)
    session.commit()
    session.refresh(item)
    return plan, day, item


# ---- plan's original 4 tests ----


def test_record_attempt_persists_with_snapshotted_limit(session, problem):
    attempt = record_attempt(
        session,
        AttemptInput(
            problem_id=problem.id, duration_bucket=DurationBucket.over, mark=Mark.C, submit_count=3
        ),
        today=date(2026, 9, 1),
    )

    assert attempt.id is not None
    assert attempt.time_limit_sec == 1200
    assert attempt.submit_count == 3


def test_record_attempt_marks_matching_plan_item_done(session, problem):
    _plan, _day, item = _make_plan_item(session, problem.topic_id, problem.id, date(2026, 9, 1))

    record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )

    session.refresh(item)
    assert item.status is ItemStatus.done


def test_record_attempt_rejects_unknown_problem(session):
    # ProblemNotFound must be a *specific* type callers can narrow to, not
    # something that also happens to catch KeyError/IndexError just because
    # they share the LookupError base class -- assert the concrete type.
    with pytest.raises(ProblemNotFound, match="problem_id=999 不存在") as exc_info:
        record_attempt(
            session,
            AttemptInput(problem_id=999, duration_bucket=DurationBucket.within, mark=Mark.A),
            today=date(2026, 9, 1),
        )
    assert type(exc_info.value) is ProblemNotFound


def test_list_history_returns_newest_first_with_problem(session, problem):
    for day in (1, 2):
        record_attempt(
            session,
            AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
            today=date(2026, 9, day),
        )

    rows = list_history(session, topic_id=problem.topic_id, limit=10)

    assert [row.attempt.attempt_date for row in rows] == [date(2026, 9, 2), date(2026, 9, 1)]
    assert rows[0].problem.lc_id == 209
    assert rows[0].first_try_ac is True


# ---- additional coverage ----


def test_record_attempt_ignores_archived_plan_item(session, problem):
    """An archived plan's PlanItem must not be picked -- the user no longer follows it."""
    _plan, _day, archived_item = _make_plan_item(
        session, problem.topic_id, problem.id, date(2026, 9, 1), status=PlanStatus.archived
    )

    record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )

    session.refresh(archived_item)
    assert archived_item.status is ItemStatus.pending


def test_record_attempt_prefers_lowest_plan_id_when_two_active_plans_collide(session, problem):
    """Two active plans scheduling the same problem on the same date is an edge
    case the schema allows. Resolution must be deterministic (lowest Plan.id),
    consistent with repositories/today.py."""
    _plan1, _day1, item1 = _make_plan_item(session, problem.topic_id, problem.id, date(2026, 9, 1))
    _plan2, _day2, item2 = _make_plan_item(session, problem.topic_id, problem.id, date(2026, 9, 1))

    record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )

    session.refresh(item1)
    session.refresh(item2)
    assert item1.status is ItemStatus.done
    assert item2.status is ItemStatus.pending


def test_record_attempt_without_matching_plan_item_still_records(session, problem):
    """Ad-hoc problem not scheduled today -- must still be recorded."""
    attempt = record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )
    assert attempt.id is not None
    assert session.exec(select(PlanItem)).all() == []


def test_record_attempt_matches_plan_item_for_injected_date_not_real_today(session, problem):
    """today= is injected; only the PlanDay for that exact date should be touched,
    even though a PlanItem exists for a different date too."""
    _plan_a, _day_a, item_today = _make_plan_item(
        session, problem.topic_id, problem.id, date(2026, 9, 1)
    )

    # A second plan/day exists for a different date -- must remain untouched.
    plan_b = Plan(topic_id=problem.topic_id, name="计划B", start_date=date(2026, 9, 5))
    session.add(plan_b)
    session.commit()
    session.refresh(plan_b)
    day_b = PlanDay(plan_id=plan_b.id, day_index=1, planned_date=date(2026, 9, 5))
    session.add(day_b)
    session.commit()
    session.refresh(day_b)
    item_other_date = PlanItem(plan_day_id=day_b.id, problem_id=problem.id)
    session.add(item_other_date)
    session.commit()
    session.refresh(item_other_date)

    record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )

    session.refresh(item_today)
    session.refresh(item_other_date)
    assert item_today.status is ItemStatus.done
    assert item_other_date.status is ItemStatus.pending


def test_record_attempt_invalid_submit_count_leaves_session_clean(session, problem):
    _plan, _day, item = _make_plan_item(session, problem.topic_id, problem.id, date(2026, 9, 1))

    with pytest.raises(ValueError):
        record_attempt(
            session,
            AttemptInput(
                problem_id=problem.id,
                duration_bucket=DurationBucket.within,
                mark=Mark.A,
                submit_count=0,
            ),
            today=date(2026, 9, 1),
        )

    assert session.exec(select(Attempt)).all() == []
    assert len(session.new) == 0
    assert len(session.dirty) == 0
    session.refresh(item)
    assert item.status is ItemStatus.pending


def test_record_attempt_negative_duration_sec_leaves_session_clean(session, problem):
    with pytest.raises(ValueError):
        record_attempt(
            session,
            AttemptInput(
                problem_id=problem.id,
                duration_bucket=DurationBucket.within,
                mark=Mark.A,
                duration_sec=-1,
            ),
            today=date(2026, 9, 1),
        )

    assert session.exec(select(Attempt)).all() == []
    assert len(session.new) == 0


def test_list_history_does_not_leak_other_topics(session, topic):
    other_topic = Topic(code="dp", name="动态规划", config_json=CONFIG_JSON.replace("sliding-window", "dp"))
    session.add(other_topic)
    session.commit()
    session.refresh(other_topic)

    p1 = Problem(
        topic_id=topic.id, lc_id=1, title="p1", url="u1",
        difficulty=Difficulty.easy, section="s1", section_name="s1",
    )
    p2 = Problem(
        topic_id=other_topic.id, lc_id=2, title="p2", url="u2",
        difficulty=Difficulty.easy, section="s1", section_name="s1",
    )
    session.add(p1)
    session.add(p2)
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    record_attempt(
        session,
        AttemptInput(problem_id=p1.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )
    record_attempt(
        session,
        AttemptInput(problem_id=p2.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )

    rows = list_history(session, topic_id=topic.id, limit=10)
    assert len(rows) == 1
    assert rows[0].problem.id == p1.id


def test_list_history_limit_is_respected(session, problem):
    for day in (1, 2, 3):
        record_attempt(
            session,
            AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
            today=date(2026, 9, day),
        )

    rows = list_history(session, topic_id=problem.topic_id, limit=2)
    assert len(rows) == 2
    assert [row.attempt.attempt_date for row in rows] == [date(2026, 9, 3), date(2026, 9, 2)]


def test_list_history_limit_zero_returns_empty(session, problem):
    record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )
    rows = list_history(session, topic_id=problem.topic_id, limit=0)
    assert rows == []


def test_list_history_topic_with_no_attempts_returns_empty(session, topic):
    rows = list_history(session, topic_id=topic.id, limit=10)
    assert rows == []


def test_list_history_same_date_ordered_by_id_desc(session, problem):
    first = record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A),
        today=date(2026, 9, 1),
    )
    second = record_attempt(
        session,
        AttemptInput(problem_id=problem.id, duration_bucket=DurationBucket.over, mark=Mark.B),
        today=date(2026, 9, 1),
    )

    rows = list_history(session, topic_id=problem.topic_id, limit=10)
    assert [row.attempt.id for row in rows] == [second.id, first.id]


def test_list_history_first_try_ac_false_on_resubmit(session, problem):
    record_attempt(
        session,
        AttemptInput(
            problem_id=problem.id, duration_bucket=DurationBucket.within, mark=Mark.A, submit_count=2
        ),
        today=date(2026, 9, 1),
    )
    rows = list_history(session, topic_id=problem.topic_id, limit=10)
    assert rows[0].first_try_ac is False
