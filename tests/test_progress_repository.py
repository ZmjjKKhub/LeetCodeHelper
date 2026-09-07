from datetime import date

import pytest

from leetcode_helper.models import (
    Attempt,
    Difficulty,
    DurationBucket,
    Mark,
    Plan,
    PlanDay,
    PlanItem,
    PlanStatus,
    Problem,
    Topic,
)
from leetcode_helper.repositories.progress import get_progress_view

CONFIG_JSON = (
    '{"code": "sliding-window", "name": "\\u6ed1\\u52a8\\u7a97\\u53e3", '
    '"time_limits": {"easy": 480, "medium": 1200, "hard": 2100}, "card_fields": []}'
)


@pytest.fixture
def topic(session):
    topic = Topic(code="sliding-window", name="滑动窗口", config_json=CONFIG_JSON)
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def add_problem(session, topic, lc_id, *, difficulty=Difficulty.medium, section="§1.1", section_name="基础"):
    problem = Problem(
        topic_id=topic.id,
        lc_id=lc_id,
        title=f"题目{lc_id}",
        url=f"https://leetcode.cn/problems/{lc_id}/",
        difficulty=difficulty,
        section=section,
        section_name=section_name,
    )
    session.add(problem)
    session.commit()
    session.refresh(problem)
    return problem


def add_attempt(
    session,
    problem,
    attempt_date,
    *,
    duration_bucket=DurationBucket.within,
    mark=Mark.A,
    submit_count=1,
):
    attempt = Attempt(
        problem_id=problem.id,
        attempt_date=attempt_date,
        duration_bucket=duration_bucket,
        time_limit_sec=1200,
        submit_count=submit_count,
        mark=mark,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def add_plan_with_days(session, topic, *, day_specs, status=PlanStatus.active, name="计划"):
    """day_specs: list of (day_index, planned_date, phase, [problems])."""
    plan = Plan(topic_id=topic.id, name=name, start_date=day_specs[0][1], status=status)
    session.add(plan)
    session.commit()
    session.refresh(plan)

    days = []
    for day_index, planned_date, phase, problems in day_specs:
        day = PlanDay(plan_id=plan.id, day_index=day_index, planned_date=planned_date, phase=phase)
        session.add(day)
        session.commit()
        session.refresh(day)
        for order, problem in enumerate(problems):
            session.add(PlanItem(plan_day_id=day.id, problem_id=problem.id, sort_order=order))
        session.commit()
        days.append(day)
    return plan, days


TODAY = date(2026, 9, 3)


# ---------------------------------------------------------------------------
# State assignment: done / today / todo
# ---------------------------------------------------------------------------


def test_states_done_today_todo(session, topic):
    attempted_earlier = add_problem(session, topic, 1)
    scheduled_today_pending = add_problem(session, topic, 2)
    scheduled_today_already_done = add_problem(session, topic, 3)
    untouched = add_problem(session, topic, 4)

    add_attempt(session, attempted_earlier, date(2026, 8, 20))
    add_attempt(session, scheduled_today_already_done, TODAY)

    add_plan_with_days(
        session,
        topic,
        day_specs=[
            (1, TODAY, "阶段一", [scheduled_today_pending, scheduled_today_already_done]),
        ],
    )

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)
    states = {
        item.problem.lc_id: item.state for section in view.sections for item in section.problems
    }

    # Attempted on an earlier date: done, not today -- even though it isn't
    # scheduled today at all.
    assert states[1] == "done"
    # Scheduled today, not yet attempted: today.
    assert states[2] == "today"
    # Scheduled today AND already attempted today: done, not today.
    assert states[3] == "done"
    # Neither attempted nor scheduled: todo.
    assert states[4] == "todo"


def test_done_item_carries_its_latest_attempt_outcome(session, topic):
    problem = add_problem(session, topic, 1)
    add_attempt(session, problem, date(2026, 8, 20), duration_bucket=DurationBucket.unsolved, mark=Mark.C)
    add_attempt(session, problem, date(2026, 8, 25), duration_bucket=DurationBucket.within, mark=Mark.A)

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)
    item = view.sections[0].problems[0]

    assert item.state == "done"
    assert item.attempt.duration_bucket is DurationBucket.within
    assert item.attempt.mark is Mark.A


# ---------------------------------------------------------------------------
# Section totals and order
# ---------------------------------------------------------------------------


def test_section_totals_and_order_match_catalogue(session, topic):
    add_problem(session, topic, 10, section="§2", section_name="第二节")
    p1 = add_problem(session, topic, 1, section="§1", section_name="第一节")
    p2 = add_problem(session, topic, 2, section="§1", section_name="第一节")
    add_problem(session, topic, 3, section="§1", section_name="第一节")
    add_attempt(session, p1, date(2026, 8, 1))
    add_attempt(session, p2, date(2026, 8, 1))

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)

    assert [s.section for s in view.sections] == ["§1", "§2"]
    section1 = view.sections[0]
    assert section1.section_name == "第一节"
    assert section1.total == 3
    assert section1.done == 2
    assert [item.problem.lc_id for item in section1.problems] == [1, 2, 3]

    section2 = view.sections[1]
    assert section2.total == 1
    assert section2.done == 0


# ---------------------------------------------------------------------------
# plan position
# ---------------------------------------------------------------------------


def test_plan_is_none_when_today_outside_any_active_plan(session, topic):
    add_problem(session, topic, 1)
    add_plan_with_days(
        session,
        topic,
        day_specs=[(1, date(2026, 8, 1), "阶段一", [])],
    )

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)

    assert view.plan is None


def test_plan_reports_day_index_and_total_days_inside_plan(session, topic):
    p1 = add_problem(session, topic, 1)
    p2 = add_problem(session, topic, 2)
    p3 = add_problem(session, topic, 3)
    _plan, days = add_plan_with_days(
        session,
        topic,
        day_specs=[
            (1, date(2026, 9, 1), "阶段一", [p1]),
            (2, date(2026, 9, 2), "阶段一", [p2]),
            (3, TODAY, "阶段一", [p3]),
            (4, date(2026, 9, 4), "阶段二", []),
            (5, date(2026, 9, 5), "阶段二", []),
        ],
    )

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)

    assert view.plan is not None
    assert view.plan.day_index == 3
    assert view.plan.total_days == 5
    assert view.plan.phase == "阶段一"
    assert view.plan.planned_date == TODAY


def test_archived_plan_does_not_count_as_inside_a_plan(session, topic):
    add_problem(session, topic, 1)
    add_plan_with_days(
        session,
        topic,
        day_specs=[(1, TODAY, "阶段一", [])],
        status=PlanStatus.archived,
    )

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)

    assert view.plan is None


# ---------------------------------------------------------------------------
# stats
# ---------------------------------------------------------------------------


def test_stats_match_hand_computed_values(session, topic):
    # 5 problems total.
    # p1: latest attempt within, submit_count=1 -> first-try AC.
    # p2: latest attempt unsolved -> counts toward unsolved, not first-try AC.
    # p3: latest attempt over, submit_count=2 -> attempted, not first-try AC
    #     (submit_count != 1), not unsolved.
    # p4: never attempted -> not counted at all.
    # p5: attempted twice: first unsolved, then within/submit_count=1 -- the
    #     *latest* attempt (within) is what stats read, so it does NOT count
    #     toward unsolved and DOES count as first-try AC.
    p1 = add_problem(session, topic, 1)
    p2 = add_problem(session, topic, 2)
    p3 = add_problem(session, topic, 3)
    add_problem(session, topic, 4)
    p5 = add_problem(session, topic, 5)

    add_attempt(session, p1, date(2026, 8, 1), duration_bucket=DurationBucket.within, mark=Mark.A, submit_count=1)
    add_attempt(session, p2, date(2026, 8, 1), duration_bucket=DurationBucket.unsolved, mark=Mark.C, submit_count=1)
    add_attempt(session, p3, date(2026, 8, 1), duration_bucket=DurationBucket.over, mark=Mark.B, submit_count=2)
    add_attempt(session, p5, date(2026, 8, 1), duration_bucket=DurationBucket.unsolved, mark=Mark.C, submit_count=1)
    add_attempt(session, p5, date(2026, 8, 5), duration_bucket=DurationBucket.within, mark=Mark.A, submit_count=1)

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)
    stats = view.stats

    assert stats.total == 5
    assert stats.attempted == 4  # p1, p2, p3, p5 (p4 untouched)
    assert stats.unsolved == 1  # only p2's latest attempt is unsolved
    assert stats.first_try_ac_count == 2  # p1 and p5's latest attempt
    assert stats.first_try_ac_rate == pytest.approx(2 / 4)


def test_stats_zero_attempted_gives_zero_rate_not_a_crash(session, topic):
    add_problem(session, topic, 1)

    view = get_progress_view(session, topic_id=topic.id, today=TODAY)

    assert view.stats.attempted == 0
    assert view.stats.first_try_ac_rate == 0.0


# ---------------------------------------------------------------------------
# misc
# ---------------------------------------------------------------------------


def test_unknown_topic_id_raises_lookup_error(session):
    with pytest.raises(LookupError):
        get_progress_view(session, topic_id=999, today=TODAY)
