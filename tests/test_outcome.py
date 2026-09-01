"""Tests for the merged 用时/掌握程度 -> Outcome control's storage mapping.

split_outcome/outcome_of are pure functions (no DB, no request) precisely so
this mapping -- the actual business rule the phase-1-entry-loop merge is
about -- can be unit-tested in isolation from the web layer.
"""

from datetime import date

import pytest

from leetcode_helper.models import Attempt, DurationBucket, Mark
from leetcode_helper.services.attempts import Outcome, first_try_ac, outcome_of, split_outcome


@pytest.mark.parametrize(
    "outcome, bucket, mark",
    [
        (Outcome.within_solid, DurationBucket.within, Mark.A),
        (Outcome.within_shaky, DurationBucket.within, Mark.B),
        (Outcome.over, DurationBucket.over, Mark.B),
        (Outcome.unsolved, DurationBucket.unsolved, Mark.C),
    ],
)
def test_split_outcome_maps_each_of_the_four_options(outcome, bucket, mark):
    assert split_outcome(outcome) == (bucket, mark)


def _attempt(bucket: DurationBucket, mark: Mark, submit_count: int = 1) -> Attempt:
    return Attempt(
        problem_id=1,
        attempt_date=date(2026, 9, 1),
        duration_bucket=bucket,
        time_limit_sec=1200,
        submit_count=submit_count,
        mark=mark,
    )


@pytest.mark.parametrize(
    "outcome",
    [Outcome.within_solid, Outcome.within_shaky, Outcome.over, Outcome.unsolved],
)
def test_outcome_of_round_trips_all_four_options(outcome):
    bucket, mark = split_outcome(outcome)
    assert outcome_of(_attempt(bucket, mark)) is outcome


def test_outcome_of_returns_none_for_within_solved_with_c_mark():
    # (within, C) -- 限时内做出来, but marked C -- is not producible by the
    # new four-option UI (within only ever pairs with A or B). Older rows or
    # direct writes can still have it; outcome_of must not crash or guess.
    assert outcome_of(_attempt(DurationBucket.within, Mark.C)) is None


def test_outcome_of_returns_none_for_over_with_a_mark():
    # (over, A) -- 超时才做出来, but marked A -- is likewise unreachable from
    # the new UI (over only ever pairs with B).
    assert outcome_of(_attempt(DurationBucket.over, Mark.A)) is None


def test_outcome_of_never_raises_for_any_valid_bucket_mark_pair():
    for bucket in DurationBucket:
        for mark in Mark:
            # Must not raise for *any* combination, reachable or not.
            outcome_of(_attempt(bucket, mark))


def test_within_solid_one_submit_is_first_try_ac():
    bucket, mark = split_outcome(Outcome.within_solid)
    assert first_try_ac(_attempt(bucket, mark, submit_count=1)) is True


def test_unsolved_is_never_first_try_ac():
    bucket, mark = split_outcome(Outcome.unsolved)
    assert first_try_ac(_attempt(bucket, mark, submit_count=1)) is False
