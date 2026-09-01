from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from leetcode_helper.models import (
    Attempt,
    AttemptKind,
    Difficulty,
    DurationBucket,
    Mark,
    Problem,
    Topic,
)


def _topic(session) -> Topic:
    topic = Topic(code="sliding-window", name="滑动窗口", config_json="{}")
    session.add(topic)
    session.commit()
    return topic


def test_problem_lc_id_unique_within_topic(session):
    topic = _topic(session)
    for _ in range(2):
        session.add(
            Problem(
                topic_id=topic.id,
                lc_id=76,
                title="最小覆盖子串",
                url="https://leetcode.cn/problems/minimum-window-substring/",
                difficulty=Difficulty.hard,
                section="§2.2",
                section_name="越长越合法/求最短/最小",
            )
        )
    with pytest.raises(IntegrityError):
        session.commit()


def test_attempt_roundtrip(session):
    topic = _topic(session)
    problem = Problem(
        topic_id=topic.id,
        lc_id=209,
        title="长度最小的子数组",
        url="https://leetcode.cn/problems/minimum-size-subarray-sum/",
        difficulty=Difficulty.medium,
        section="§2.2",
        section_name="越长越合法/求最短/最小",
    )
    session.add(problem)
    session.commit()

    session.add(
        Attempt(
            problem_id=problem.id,
            attempt_date=date(2026, 8, 31),
            kind=AttemptKind.new,
            duration_bucket=DurationBucket.within,
            time_limit_sec=1200,
            submit_count=2,
            mark=Mark.B,
            used_template="C",
        )
    )
    session.commit()

    loaded = session.get(Attempt, 1)
    assert loaded.duration_bucket is DurationBucket.within
    assert loaded.duration_sec is None
    assert loaded.mark is Mark.B
