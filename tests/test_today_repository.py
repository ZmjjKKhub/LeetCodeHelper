from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine

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
from leetcode_helper.repositories.today import get_today_view


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


@pytest.fixture
def topic(session):
    topic = Topic(
        code="sliding-window",
        name="滑动窗口",
        config_json=(
            '{"code": "sliding-window", "name": "\\u6ed1\\u52a8\\u7a97\\u53e3", '
            '"time_limits": {"easy": 480, "medium": 1200, "hard": 2100}, "card_fields": []}'
        ),
    )
    session.add(topic)
    session.commit()
    session.refresh(topic)
    return topic


def add_problem(session, topic, lc_id, *, difficulty=Difficulty.medium, section="§2.2"):
    problem = Problem(
        topic_id=topic.id,
        lc_id=lc_id,
        title=f"题目{lc_id}",
        url=f"https://leetcode.cn/problems/{lc_id}/",
        difficulty=difficulty,
        section=section,
        section_name="小节名",
        default_template="C",
    )
    session.add(problem)
    session.commit()
    session.refresh(problem)
    return problem


def add_plan(session, topic, planned_date, *, status=PlanStatus.active, name="计划"):
    plan = Plan(topic_id=topic.id, name=name, start_date=planned_date, status=status)
    session.add(plan)
    session.commit()
    session.refresh(plan)
    return plan


def add_plan_day_for_plan(session, plan, planned_date, problems, *, theme="今日主题", day_index=1):
    day = PlanDay(
        plan_id=plan.id,
        day_index=day_index,
        planned_date=planned_date,
        phase="阶段一",
        theme=theme,
    )
    session.add(day)
    session.commit()
    session.refresh(day)

    for order, problem in enumerate(problems):
        session.add(PlanItem(plan_day_id=day.id, problem_id=problem.id, sort_order=order))
    session.commit()
    return day


def add_plan_day(session, topic, planned_date, problems, *, theme="今日主题"):
    plan = add_plan(session, topic, planned_date)
    return add_plan_day_for_plan(session, plan, planned_date, problems, theme=theme)


# ---------------------------------------------------------------------------
# Plan's original 4 tests
# ---------------------------------------------------------------------------


def test_planned_day_returns_its_items_in_order(session, topic):
    p1 = add_problem(session, topic, 209)
    p2 = add_problem(session, topic, 3)
    add_plan_day(session, topic, date(2026, 9, 1), [p2, p1])

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.is_fallback is False
    assert view.phase == "阶段一"
    assert view.theme == "今日主题"
    assert [item.problem.lc_id for item in view.items] == [3, 209]
    assert view.items[0].time_limit_sec == 1200
    assert view.items[0].attempt is None


def test_item_carries_todays_attempt(session, topic):
    problem = add_problem(session, topic, 209)
    add_plan_day(session, topic, date(2026, 9, 1), [problem])
    session.add(
        Attempt(
            problem_id=problem.id,
            attempt_date=date(2026, 9, 1),
            duration_bucket=DurationBucket.within,
            time_limit_sec=1200,
            mark=Mark.A,
        )
    )
    session.commit()

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.items[0].attempt is not None
    assert view.items[0].attempt.mark is Mark.A


def test_fallback_lists_untouched_problems_when_no_plan_day(session, topic):
    solved = add_problem(session, topic, 209)
    add_problem(session, topic, 3, section="§2.1")
    add_problem(session, topic, 76, difficulty=Difficulty.hard, section="§2.2")
    session.add(
        Attempt(
            problem_id=solved.id,
            attempt_date=date(2026, 8, 20),
            duration_bucket=DurationBucket.within,
            time_limit_sec=1200,
            mark=Mark.A,
        )
    )
    session.commit()

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.is_fallback is True
    assert [item.problem.lc_id for item in view.items] == [3, 76]
    assert view.items[1].time_limit_sec == 2100


def test_fallback_groups_by_section(session, topic):
    add_problem(session, topic, 3, section="§2.1")
    add_problem(session, topic, 76, section="§2.2")
    add_problem(session, topic, 209, section="§2.2")

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert [(section, [i.problem.lc_id for i in items]) for section, items in view.grouped()] == [
        ("§2.1", [3]),
        ("§2.2", [76, 209]),
    ]


# ---------------------------------------------------------------------------
# Additional coverage
# ---------------------------------------------------------------------------


def test_multiple_attempts_today_latest_wins(session, topic):
    """A problem attempted twice today: the item's `attempt` should reflect the
    most recent submission, since the UI shows "already logged" state and a
    later re-attempt supersedes an earlier one on the same day."""
    problem = add_problem(session, topic, 209)
    add_plan_day(session, topic, date(2026, 9, 1), [problem])
    session.add(
        Attempt(
            problem_id=problem.id,
            attempt_date=date(2026, 9, 1),
            duration_bucket=DurationBucket.over,
            time_limit_sec=1200,
            mark=Mark.C,
        )
    )
    session.commit()
    session.add(
        Attempt(
            problem_id=problem.id,
            attempt_date=date(2026, 9, 1),
            duration_bucket=DurationBucket.within,
            time_limit_sec=1200,
            mark=Mark.A,
        )
    )
    session.commit()

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.items[0].attempt is not None
    assert view.items[0].attempt.mark is Mark.A


def test_two_active_plans_with_same_date_is_deterministic(session, topic):
    """Nothing in the schema prevents two plans on the same topic from both
    landing a PlanDay on the same calendar date (day_index uniqueness is
    per-plan). This is a data anomaly, but the query must still resolve it
    deterministically rather than depend on DB row order."""
    p1 = add_problem(session, topic, 209)
    p2 = add_problem(session, topic, 3)

    plan_a = add_plan(session, topic, date(2026, 9, 1), name="计划A")
    plan_b = add_plan(session, topic, date(2026, 9, 1), name="计划B")
    add_plan_day_for_plan(session, plan_a, date(2026, 9, 1), [p1], theme="来自A")
    add_plan_day_for_plan(session, plan_b, date(2026, 9, 1), [p2], theme="来自B")

    view1 = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))
    view2 = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    # Deterministic: repeated calls return the same plan's day.
    assert view1.theme == view2.theme
    # The earlier-created (lower id) plan wins.
    assert view1.theme == "来自A"


def test_archived_plan_does_not_drive_today_and_falls_back(session, topic):
    """An archived plan's PlanDay must not surface as today's planned items —
    the plan is done/abandoned, so today's page should fall back to the
    untouched-problems view instead."""
    p1 = add_problem(session, topic, 209, section="§2.1")
    plan = add_plan(session, topic, date(2026, 9, 1), status=PlanStatus.archived)
    add_plan_day_for_plan(session, plan, date(2026, 9, 1), [p1])

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.is_fallback is True
    assert [item.problem.lc_id for item in view.items] == [209]


def test_archived_plan_ignored_even_when_active_plan_also_matches(session, topic):
    p1 = add_problem(session, topic, 209)
    p2 = add_problem(session, topic, 3)

    archived_plan = add_plan(session, topic, date(2026, 9, 1), status=PlanStatus.archived)
    add_plan_day_for_plan(session, archived_plan, date(2026, 9, 1), [p1], theme="旧计划")

    active_plan = add_plan(session, topic, date(2026, 9, 1), status=PlanStatus.active)
    add_plan_day_for_plan(session, active_plan, date(2026, 9, 1), [p2], theme="新计划")

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.is_fallback is False
    assert view.theme == "新计划"
    assert [item.problem.lc_id for item in view.items] == [3]


def test_planned_day_with_zero_items_is_not_fallback(session, topic):
    add_problem(session, topic, 209)  # exists in topic but not scheduled today
    add_plan_day(session, topic, date(2026, 9, 1), [])

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert view.is_fallback is False
    assert view.items == []


def test_grouped_orders_by_lc_id_within_section_regardless_of_insertion_order(session, topic):
    add_problem(session, topic, 76, section="§2.2")
    add_problem(session, topic, 3, section="§2.2")
    add_problem(session, topic, 209, section="§2.2")
    add_problem(session, topic, 42, section="§2.1")  # single-problem section

    view = get_today_view(session, topic_id=topic.id, today=date(2026, 9, 1))

    assert [(section, [i.problem.lc_id for i in items]) for section, items in view.grouped()] == [
        ("§2.1", [42]),
        ("§2.2", [3, 76, 209]),
    ]


def test_unknown_topic_id_raises_lookup_error(session):
    with pytest.raises(LookupError):
        get_today_view(session, topic_id=999, today=date(2026, 9, 1))
