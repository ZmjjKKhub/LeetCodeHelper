from datetime import date

import pytest

from leetcode_helper.models import Attempt, AttemptKind, Difficulty, DurationBucket, Mark
from leetcode_helper.services.attempts import AttemptInput, build_attempt, first_try_ac
from leetcode_helper.services.topics import parse_topic_config

CONFIG = parse_topic_config(
    {
        "code": "sliding-window",
        "name": "滑动窗口",
        "time_limits": {"easy": 480, "medium": 1200, "hard": 2100},
        "card_fields": [],
    }
)


def test_build_attempt_snapshots_time_limit():
    attempt = build_attempt(
        AttemptInput(
            problem_id=7,
            duration_bucket=DurationBucket.within,
            mark=Mark.A,
        ),
        difficulty=Difficulty.medium,
        config=CONFIG,
        today=date(2026, 8, 31),
    )
    assert attempt.problem_id == 7
    assert attempt.time_limit_sec == 1200
    assert attempt.attempt_date == date(2026, 8, 31)
    assert attempt.kind is AttemptKind.new
    assert attempt.submit_count == 1
    assert attempt.duration_sec is None
    assert attempt.id is None


def test_build_attempt_keeps_optional_precise_duration():
    attempt = build_attempt(
        AttemptInput(
            problem_id=7,
            duration_bucket=DurationBucket.over,
            mark=Mark.C,
            submit_count=4,
            used_template="C",
            duration_sec=1830,
        ),
        difficulty=Difficulty.medium,
        config=CONFIG,
        today=date(2026, 8, 31),
    )
    assert attempt.duration_sec == 1830
    assert attempt.used_template == "C"
    assert attempt.submit_count == 4


def test_submit_count_must_be_positive():
    with pytest.raises(ValueError, match="submit_count 必须 >= 1"):
        build_attempt(
            AttemptInput(
                problem_id=7,
                duration_bucket=DurationBucket.within,
                mark=Mark.A,
                submit_count=0,
            ),
            difficulty=Difficulty.easy,
            config=CONFIG,
            today=date(2026, 8, 31),
        )


def _attempt(bucket: DurationBucket, submit_count: int) -> Attempt:
    return Attempt(
        problem_id=1,
        attempt_date=date(2026, 8, 31),
        duration_bucket=bucket,
        time_limit_sec=1200,
        submit_count=submit_count,
        mark=Mark.A,
    )


def test_first_try_ac_true_only_for_single_submit_and_solved():
    assert first_try_ac(_attempt(DurationBucket.within, 1)) is True
    assert first_try_ac(_attempt(DurationBucket.over, 1)) is True


def test_first_try_ac_false_when_multiple_submits_or_unsolved():
    assert first_try_ac(_attempt(DurationBucket.within, 2)) is False
    assert first_try_ac(_attempt(DurationBucket.unsolved, 1)) is False
