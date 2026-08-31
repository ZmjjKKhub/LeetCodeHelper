"""由表单输入构造 Attempt。纯函数，不接受 Session。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from leetcode_helper.models import Attempt, AttemptKind, Difficulty, DurationBucket, Mark
from leetcode_helper.services.topics import TopicConfig, time_limit_for


@dataclass(frozen=True)
class AttemptInput:
    problem_id: int
    duration_bucket: DurationBucket
    mark: Mark
    submit_count: int = 1
    used_template: str | None = None
    duration_sec: int | None = None


def build_attempt(
    data: AttemptInput,
    *,
    difficulty: Difficulty,
    config: TopicConfig,
    today: date,
    kind: AttemptKind = AttemptKind.new,
    review_task_id: int | None = None,
) -> Attempt:
    if data.submit_count < 1:
        raise ValueError(f"submit_count 必须 >= 1，实际是 {data.submit_count}")
    if data.duration_sec is not None and data.duration_sec < 0:
        raise ValueError(f"duration_sec 不能为负，实际是 {data.duration_sec}")

    return Attempt(
        problem_id=data.problem_id,
        attempt_date=today,
        kind=kind,
        review_task_id=review_task_id,
        duration_bucket=data.duration_bucket,
        duration_sec=data.duration_sec,
        time_limit_sec=time_limit_for(config, difficulty),
        submit_count=data.submit_count,
        mark=data.mark,
        used_template=data.used_template or None,
    )


def first_try_ac(attempt: Attempt) -> bool:
    """派生量，不落库。见规格 §4.3。"""
    return attempt.submit_count == 1 and attempt.duration_bucket is not DurationBucket.unsolved
