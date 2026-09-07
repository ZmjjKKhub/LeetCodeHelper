"""Repository dataclass/model -> JSON schema conversion.

Kept separate from the routers so the mapping (what a "problem" or a "today
item" looks like on the wire) is defined once and reused by every endpoint
that emits one -- /api/today and POST /api/attempts both emit TodayItemOut,
for instance.
"""

from __future__ import annotations

from datetime import date as date_type

from leetcode_helper.models import Attempt, Problem, Topic
from leetcode_helper.repositories.attempts import HistoryRow
from leetcode_helper.repositories.today import TodayItem, TodayView
from leetcode_helper.services.attempts import outcome_of

from .schemas import (
    AttemptOut,
    HistoryRowOut,
    ProblemOut,
    TodayItemOut,
    TodayOut,
    TopicOut,
)


def to_problem_out(problem: Problem) -> ProblemOut:
    return ProblemOut(
        id=problem.id,
        lc_id=problem.lc_id,
        title=problem.title,
        url=problem.url,
        difficulty=problem.difficulty.value,
        section=problem.section,
        section_name=problem.section_name,
        is_starred=problem.is_starred,
        is_optional=problem.is_optional,
    )


def to_attempt_out(attempt: Attempt) -> AttemptOut:
    outcome = outcome_of(attempt)
    return AttemptOut(
        outcome=outcome.value if outcome is not None else None,
        submit_count=attempt.submit_count,
        used_template=attempt.used_template,
    )


def to_today_item_out(item: TodayItem) -> TodayItemOut:
    return TodayItemOut(
        problem=to_problem_out(item.problem),
        time_limit_sec=item.time_limit_sec,
        is_done=item.is_done,
        derived_template=item.problem.default_template,
        attempt=to_attempt_out(item.attempt) if item.attempt is not None else None,
    )


def to_today_out(topic: Topic, today: date_type, view: TodayView) -> TodayOut:
    return TodayOut(
        topic=TopicOut(code=topic.code, name=topic.name),
        date=today,
        is_fallback=view.is_fallback,
        phase=view.phase,
        theme=view.theme,
        items=[to_today_item_out(item) for item in view.items],
    )


def to_history_row_out(row: HistoryRow) -> HistoryRowOut:
    return HistoryRowOut(
        date=row.attempt.attempt_date,
        problem=to_problem_out(row.problem),
        duration_bucket=row.attempt.duration_bucket.value,
        mark=row.attempt.mark.value,
        submit_count=row.attempt.submit_count,
        used_template=row.attempt.used_template,
        first_try_ac=row.first_try_ac,
    )
