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
from leetcode_helper.repositories.progress import (
    ProgressPlanPosition,
    ProgressProblemItem,
    ProgressSectionView,
    ProgressStats,
    ProgressView,
)
from leetcode_helper.repositories.today import TodayItem, TodayView
from leetcode_helper.services.attempts import outcome_of

from .schemas import (
    AttemptOut,
    HistoryRowOut,
    ProblemOut,
    ProgressOut,
    ProgressPlanOut,
    ProgressProblemOut,
    ProgressSectionOut,
    ProgressStatsOut,
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


def to_progress_problem_out(item: ProgressProblemItem) -> ProgressProblemOut:
    outcome = outcome_of(item.attempt) if item.attempt is not None else None
    return ProgressProblemOut(
        lc_id=item.problem.lc_id,
        title=item.problem.title,
        state=item.state,
        outcome=outcome.value if outcome is not None else None,
    )


def to_progress_section_out(section: ProgressSectionView) -> ProgressSectionOut:
    return ProgressSectionOut(
        section=section.section,
        section_name=section.section_name,
        total=section.total,
        done=section.done,
        problems=[to_progress_problem_out(item) for item in section.problems],
    )


def to_progress_plan_out(plan: ProgressPlanPosition | None) -> ProgressPlanOut | None:
    if plan is None:
        return None
    return ProgressPlanOut(
        day_index=plan.day_index,
        total_days=plan.total_days,
        phase=plan.phase,
        planned_date=plan.planned_date,
    )


def to_progress_stats_out(stats: ProgressStats) -> ProgressStatsOut:
    return ProgressStatsOut(
        total=stats.total,
        attempted=stats.attempted,
        unsolved=stats.unsolved,
        first_try_ac_count=stats.first_try_ac_count,
        first_try_ac_rate=stats.first_try_ac_rate,
    )


def to_progress_out(topic: Topic, view: ProgressView) -> ProgressOut:
    return ProgressOut(
        topic=TopicOut(code=topic.code, name=topic.name),
        plan=to_progress_plan_out(view.plan),
        sections=[to_progress_section_out(section) for section in view.sections],
        stats=to_progress_stats_out(view.stats),
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
