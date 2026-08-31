"""今日页的数据查询。"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from itertools import groupby

from sqlmodel import Session, select

from leetcode_helper.models import Attempt, Plan, PlanDay, PlanItem, PlanStatus, Problem, Topic
from leetcode_helper.services.topics import TopicConfig, parse_topic_config_json, time_limit_for


@dataclass
class TodayItem:
    problem: Problem
    time_limit_sec: int
    plan_item_id: int | None = None
    attempt: Attempt | None = None

    @property
    def is_done(self) -> bool:
        return self.attempt is not None


@dataclass
class TodayView:
    config: TopicConfig
    items: list[TodayItem] = field(default_factory=list)
    is_fallback: bool = False
    phase: str = ""
    theme: str = ""
    plan_day_id: int | None = None

    def grouped(self) -> list[tuple[str, list[TodayItem]]]:
        ordered = sorted(self.items, key=lambda i: (i.problem.section, i.problem.lc_id))
        return [
            (section, list(items))
            for section, items in groupby(ordered, key=lambda i: i.problem.section)
        ]


def _todays_attempts(session: Session, problem_ids: list[int], today: date) -> dict[int, Attempt]:
    """One attempt per problem for `today`. When a problem was attempted more
    than once today, the *latest* attempt (highest id) wins: the UI shows the
    current "already logged" state for the day, and a later re-attempt is the
    up-to-date one. Sorting ascending by id and letting the dict overwrite
    achieves that.
    """
    if not problem_ids:
        return {}
    rows = session.exec(
        select(Attempt)
        .where(Attempt.problem_id.in_(problem_ids), Attempt.attempt_date == today)
        .order_by(Attempt.id)
    ).all()
    return {attempt.problem_id: attempt for attempt in rows}


def get_today_view(session: Session, *, topic_id: int, today: date) -> TodayView:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise LookupError(f"topic_id={topic_id} 不存在")
    config = parse_topic_config_json(topic.config_json)

    # Only an *active* plan may drive today's page. An archived plan is done
    # or abandoned; leaving its old PlanDay in the query would silently pin
    # today's page to a plan the user no longer follows. When more than one
    # active plan's PlanDay lands on the same date (schema allows it: the
    # day_index uniqueness is per-plan, not per-date), resolve deterministically
    # by the lowest Plan.id, then the lowest PlanDay.id — instead of depending
    # on unspecified DB row order.
    day = session.exec(
        select(PlanDay)
        .join(Plan, Plan.id == PlanDay.plan_id)
        .where(
            Plan.topic_id == topic_id,
            Plan.status == PlanStatus.active,
            PlanDay.planned_date == today,
        )
        .order_by(Plan.id, PlanDay.id)
    ).first()

    if day is not None:
        rows = session.exec(
            select(PlanItem, Problem)
            .join(Problem, Problem.id == PlanItem.problem_id)
            .where(PlanItem.plan_day_id == day.id)
            .order_by(PlanItem.sort_order, PlanItem.id)
        ).all()
        attempts = _todays_attempts(session, [problem.id for _, problem in rows], today)
        items = [
            TodayItem(
                problem=problem,
                time_limit_sec=time_limit_for(config, problem.difficulty),
                plan_item_id=plan_item.id,
                attempt=attempts.get(problem.id),
            )
            for plan_item, problem in rows
        ]
        return TodayView(
            config=config,
            items=items,
            is_fallback=False,
            phase=day.phase,
            theme=day.theme,
            plan_day_id=day.id,
        )

    attempted_ids = set(
        session.exec(
            select(Attempt.problem_id)
            .join(Problem, Problem.id == Attempt.problem_id)
            .where(Problem.topic_id == topic_id)
        ).all()
    )
    problems = session.exec(
        select(Problem)
        .where(Problem.topic_id == topic_id)
        .order_by(Problem.section, Problem.lc_id)
    ).all()
    items = [
        TodayItem(problem=problem, time_limit_sec=time_limit_for(config, problem.difficulty))
        for problem in problems
        if problem.id not in attempted_ids
    ]
    return TodayView(config=config, items=items, is_fallback=True)
