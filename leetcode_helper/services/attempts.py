"""由表单输入构造 Attempt。纯函数，不接受 Session。"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import date

from leetcode_helper.models import Attempt, AttemptKind, Difficulty, DurationBucket, Mark
from leetcode_helper.services.topics import TopicConfig, time_limit_for


class Outcome(str, enum.Enum):
    """The single "今天做得怎么样？" choice the entry panel now asks.

    This replaces the old two-question 用时/掌握程度 pair in the *UI* only --
    duration_bucket and mark stay separate columns on Attempt (Phase 2's R2
    rule reads the bucket, and the planned FSRS scheduler wants both raw
    signals), so this enum is a pure presentation-to-storage mapping, not a
    schema change. within_shaky exists specifically to keep "限时内做出来了，
    但是靠硬套模板/蒙的，没真懂" from being recorded as a clean A that never
    gets a review scheduled -- see split_outcome below.
    """

    within_solid = "within_solid"
    within_shaky = "within_shaky"
    over = "over"
    unsolved = "unsolved"


# (duration_bucket, mark) for each Outcome. Kept as one explicit table (not
# scattered if/elif branches) so split_outcome and outcome_of can both be
# built from -- and checked against -- the same source of truth.
_OUTCOME_TO_PAIR: dict[Outcome, tuple[DurationBucket, Mark]] = {
    Outcome.within_solid: (DurationBucket.within, Mark.A),
    Outcome.within_shaky: (DurationBucket.within, Mark.B),
    Outcome.over: (DurationBucket.over, Mark.B),
    Outcome.unsolved: (DurationBucket.unsolved, Mark.C),
}
assert set(_OUTCOME_TO_PAIR) == set(Outcome), "_OUTCOME_TO_PAIR 未覆盖所有 Outcome 枚举值"

_PAIR_TO_OUTCOME: dict[tuple[DurationBucket, Mark], Outcome] = {
    pair: outcome for outcome, pair in _OUTCOME_TO_PAIR.items()
}


def split_outcome(outcome: Outcome) -> tuple[DurationBucket, Mark]:
    """The one four-option control's storage mapping. See the table above."""
    return _OUTCOME_TO_PAIR[outcome]


def outcome_of(attempt: Attempt) -> Outcome | None:
    """Inverse of split_outcome, for rendering a done row's current option.

    Total and never raises: (duration_bucket, mark) combinations the new UI
    cannot produce -- e.g. (within, C) or (over, A), reachable only via older
    rows, direct DB edits, or Phase-2 review-flow writes -- have no matching
    Outcome. Return None for those rather than guessing; the template then
    simply marks no option as current instead of showing a wrong one.
    """
    return _PAIR_TO_OUTCOME.get((attempt.duration_bucket, attempt.mark))


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
    """由表单输入构造一条 Attempt。

    注意：duration_bucket 与 duration_sec 允许不一致（例如 duration_bucket=within
    但 duration_sec=9999）——这是有意为之。duration_bucket 是权威信号，
    duration_sec 只是可选的精确记录，不要在这里加二者一致性的校验。
    """
    if isinstance(data.submit_count, bool) or data.submit_count < 1:
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
