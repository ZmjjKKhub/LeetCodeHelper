"""JSON 响应/请求的显式类型定义。

Plain (stdlib) dataclasses for every *response* shape -- FastAPI serializes
these the same way it does a Pydantic model (converting via its internal
pydantic-dataclass machinery), so there is no need to reach for BaseModel
just to get typed, documented output. They deliberately do not reuse the
repository dataclasses (TodayItem, TodayView, HistoryRow, ...) directly:
those carry full SQLModel rows (e.g. TodayItem.problem is a `Problem` table
row) and are shaped for the Jinja templates, not for a stable public JSON
contract. leetcode_helper/api/converters.py maps one to the other.

AttemptCreateIn is the one exception -- it is a *request* body, where
pydantic's own validation (and its resulting 422 error shape) is the actual
behavior wanted, not just typing.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date as date_type

from pydantic import BaseModel

from leetcode_helper.services.attempts import Outcome


@dataclass(frozen=True)
class ProblemOut:
    id: int
    lc_id: int
    title: str
    url: str
    difficulty: str
    section: str
    section_name: str
    is_starred: bool
    is_optional: bool


@dataclass(frozen=True)
class AttemptOut:
    # None when the stored (duration_bucket, mark) pair is one the current
    # four-option UI cannot itself produce (an older row, or a direct DB /
    # Phase-2-review write) -- see services.attempts.outcome_of. The API
    # reports that as an honest "no outcome" rather than guessing.
    outcome: str | None
    submit_count: int
    used_template: str | None


@dataclass(frozen=True)
class TodayItemOut:
    problem: ProblemOut
    time_limit_sec: int
    is_done: bool
    # The problem's judged/derived template (Problem.default_template) --
    # lets the frontend show "原本预期 X" when it differs from attempt.used_template.
    derived_template: str | None
    attempt: AttemptOut | None


@dataclass(frozen=True)
class TopicOut:
    code: str
    name: str


@dataclass(frozen=True)
class TodayOut:
    topic: TopicOut
    date: date_type
    is_fallback: bool
    phase: str
    theme: str
    items: list[TodayItemOut]


@dataclass(frozen=True)
class HistoryRowOut:
    date: date_type
    problem: ProblemOut
    duration_bucket: str
    mark: str
    submit_count: int
    used_template: str | None
    first_try_ac: bool


@dataclass(frozen=True)
class HistoryOut:
    rows: list[HistoryRowOut]
    limit: int
    truncated: bool


@dataclass(frozen=True)
class TemplateOut:
    code: str
    name: str
    trigger_signal: str


@dataclass(frozen=True)
class OutcomeOut:
    value: str
    label: str
    consequence: str


@dataclass(frozen=True)
class MetaOut:
    topic: TopicOut
    templates: list[TemplateOut]
    outcomes: list[OutcomeOut]


@dataclass(frozen=True)
class ProgressPlanOut:
    day_index: int
    total_days: int
    phase: str
    planned_date: date_type


@dataclass(frozen=True)
class ProgressProblemOut:
    lc_id: int
    title: str
    # "done" | "today" | "todo" -- see repositories/progress.py's ProblemState.
    state: str
    # Same None-when-unmappable rule as AttemptOut.outcome; always None when
    # state != "done".
    outcome: str | None


@dataclass(frozen=True)
class ProgressSectionOut:
    section: str
    section_name: str
    total: int
    done: int
    problems: list[ProgressProblemOut]


@dataclass(frozen=True)
class ProgressStatsOut:
    total: int
    attempted: int
    unsolved: int
    first_try_ac_count: int
    # Fraction in [0, 1], not a percentage -- the frontend formats it
    # (Math.round(rate * 100)), same division of labour as HistoryOut.rows'
    # per-row first_try_ac booleans, whose percentage the frontend already
    # computes itself (see History.tsx).
    first_try_ac_rate: float


@dataclass(frozen=True)
class ProgressOut:
    topic: TopicOut
    # None exactly when today falls outside any active plan (fallback mode) --
    # see repositories/progress.py::ProgressView.plan.
    plan: ProgressPlanOut | None
    sections: list[ProgressSectionOut]
    stats: ProgressStatsOut


class AttemptCreateIn(BaseModel):
    """POST /api/attempts request body. Same semantics as the existing
    HTML form POST to /attempts (see web/routes/today.py) -- including
    update-in-place when an attempt already exists for the problem today.
    """

    problem_id: int
    outcome: Outcome
    submit_count: int = 1
    used_template: str | None = None
