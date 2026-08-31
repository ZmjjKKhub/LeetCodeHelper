"""SQLModel 表定义。Phase 1 只覆盖静态数据、计划、做题记录三组表。"""

from __future__ import annotations

import enum
from datetime import date, datetime, timezone

from sqlmodel import Field, SQLModel, UniqueConstraint


def _now() -> datetime:
    return datetime.now(timezone.utc)


class Difficulty(str, enum.Enum):
    easy = "easy"
    medium = "medium"
    hard = "hard"


class Mark(str, enum.Enum):
    A = "A"
    B = "B"
    C = "C"


class DurationBucket(str, enum.Enum):
    within = "within"
    over = "over"
    unsolved = "unsolved"


class AttemptKind(str, enum.Enum):
    new = "new"
    review = "review"


class PlanStatus(str, enum.Enum):
    active = "active"
    archived = "archived"


class DayStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    skipped = "skipped"
    postponed = "postponed"


class ItemStatus(str, enum.Enum):
    pending = "pending"
    done = "done"
    deferred = "deferred"


class Topic(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)
    name: str
    config_json: str
    is_active: bool = True


class Problem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("topic_id", "lc_id"),)

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    lc_id: int
    title: str
    url: str
    difficulty: Difficulty
    section: str
    section_name: str
    is_starred: bool = False
    is_premium: bool = False
    is_optional: bool = False
    default_template: str | None = None


class Template(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("topic_id", "code"),)

    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    code: str
    name: str
    language: str = "python"
    content: str = ""
    pitfalls: str = ""
    trigger_signal: str = ""
    current_version: int = 1
    updated_at: datetime = Field(default_factory=_now)


class Plan(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    topic_id: int = Field(foreign_key="topic.id", index=True)
    name: str
    start_date: date
    status: PlanStatus = PlanStatus.active


class PlanDay(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_id", "day_index"),)

    id: int | None = Field(default=None, primary_key=True)
    plan_id: int = Field(foreign_key="plan.id", index=True)
    day_index: int
    planned_date: date = Field(index=True)
    actual_date: date | None = None
    phase: str = ""
    theme: str = ""
    status: DayStatus = DayStatus.pending


class PlanItem(SQLModel, table=True):
    __table_args__ = (UniqueConstraint("plan_day_id", "problem_id"),)

    id: int | None = Field(default=None, primary_key=True)
    plan_day_id: int = Field(foreign_key="planday.id", index=True)
    problem_id: int = Field(foreign_key="problem.id", index=True)
    sort_order: int = 0
    status: ItemStatus = ItemStatus.pending


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    problem_id: int = Field(foreign_key="problem.id", index=True)
    attempt_date: date = Field(index=True)
    kind: AttemptKind = AttemptKind.new
    review_task_id: int | None = None
    duration_bucket: DurationBucket
    duration_sec: int | None = None
    time_limit_sec: int
    submit_count: int = 1
    mark: Mark
    used_template: str | None = None
    created_at: datetime = Field(default_factory=_now)
