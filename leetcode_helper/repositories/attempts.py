"""Attempt 的写入与历史查询。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlmodel import Session, select

from leetcode_helper.models import (
    Attempt,
    AttemptKind,
    ItemStatus,
    Plan,
    PlanDay,
    PlanItem,
    PlanStatus,
    Problem,
    Topic,
)
from leetcode_helper.services.attempts import AttemptInput, build_attempt, first_try_ac
from leetcode_helper.services.topics import parse_topic_config_json


@dataclass
class HistoryRow:
    attempt: Attempt
    problem: Problem
    first_try_ac: bool


def record_attempt(
    session: Session,
    data: AttemptInput,
    *,
    today: date,
    kind: AttemptKind = AttemptKind.new,
) -> Attempt:
    problem = session.get(Problem, data.problem_id)
    if problem is None:
        raise LookupError(f"problem_id={data.problem_id} 不存在")

    topic = session.get(Topic, problem.topic_id)
    config = parse_topic_config_json(topic.config_json)

    # build_attempt is pure and validates its input (submit_count, duration_sec)
    # before any Attempt object is constructed. If it raises, nothing has been
    # added to the session yet, so the session stays clean -- no rollback needed.
    attempt = build_attempt(
        data, difficulty=problem.difficulty, config=config, today=today, kind=kind
    )
    session.add(attempt)

    # Only an *active* plan's PlanItem may be marked done. An archived plan is
    # done or abandoned; matching against it would silently resurrect a plan
    # the user no longer follows (see repositories/today.py for the same
    # reasoning). When more than one active plan schedules the same problem on
    # the same date (the schema allows this: day_index uniqueness is per-plan,
    # not per-date), resolve deterministically by the lowest Plan.id, then the
    # lowest PlanDay.id/PlanItem.id -- instead of relying on unspecified DB row
    # order from a bare `.first()`.
    plan_item = session.exec(
        select(PlanItem)
        .join(PlanDay, PlanDay.id == PlanItem.plan_day_id)
        .join(Plan, Plan.id == PlanDay.plan_id)
        .where(
            PlanItem.problem_id == problem.id,
            PlanDay.planned_date == today,
            Plan.status == PlanStatus.active,
        )
        .order_by(Plan.id, PlanDay.id, PlanItem.id)
    ).first()
    if plan_item is not None:
        plan_item.status = ItemStatus.done
        session.add(plan_item)

    session.commit()
    session.refresh(attempt)
    return attempt


def list_history(session: Session, *, topic_id: int, limit: int = 200) -> list[HistoryRow]:
    rows = session.exec(
        select(Attempt, Problem)
        .join(Problem, Problem.id == Attempt.problem_id)
        .where(Problem.topic_id == topic_id)
        .order_by(Attempt.attempt_date.desc(), Attempt.id.desc())
        .limit(limit)
    ).all()
    return [
        HistoryRow(attempt=attempt, problem=problem, first_try_ac=first_try_ac(attempt))
        for attempt, problem in rows
    ]
