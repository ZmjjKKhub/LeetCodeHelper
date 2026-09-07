"""Shared fixtures for the web-layer tests.

`engine`, `CONFIG_JSON`, and the seeded-problem setup used to be copy-pasted
into every test_web_*.py file. That copy-paste is exactly how the StaticPool
bug (see the `engine` fixture below) silently propagated from one test file
to the next -- one file had it, a second was written by copying the first
minus the fix. Hoisting it here means there is exactly one place to get it
right.
"""

from __future__ import annotations

from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from leetcode_helper.models import Difficulty, Plan, PlanDay, PlanItem, Problem, Topic
from leetcode_helper.web.app_factory import create_app

CONFIG_JSON = (
    '{"code": "sliding-window", "name": "\\u6ed1\\u52a8\\u7a97\\u53e3", '
    '"time_limits": {"easy": 480, "medium": 1200, "hard": 2100}, "card_fields": []}'
)


@pytest.fixture
def session():
    # Plain (non-StaticPool) in-memory engine for repository/model/importer
    # tests, which never cross threads the way the web `engine` fixture
    # above does. Was copy-pasted identically into test_attempt_repository,
    # test_models, test_seed_importer and test_today_repository -- hoisted
    # here so there is exactly one place to get it right.
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


# A config missing the "hard" time limit -- parse_topic_config_json requires
# all three Difficulty values to be present, so this fails to parse no
# matter which difficulty the problem being attempted actually is.
CORRUPT_CONFIG_JSON = (
    '{"code": "sliding-window", "name": "\\u6ed1\\u52a8\\u7a97\\u53e3", '
    '"time_limits": {"easy": 480, "medium": 1200}, "card_fields": []}'
)

TODAY = date(2026, 9, 1)


@pytest.fixture
def engine():
    # StaticPool is required (not just check_same_thread=False): TestClient
    # dispatches requests on a different thread than the test body, and the
    # default SingletonThreadPool for sqlite ":memory:" hands each thread its
    # own separate in-memory database -- rows written on one thread would be
    # invisible on the other. StaticPool shares one connection across
    # threads.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed(
    engine,
    *,
    with_plan: bool,
    is_active: bool = True,
    config_json: str = CONFIG_JSON,
    lc_id: int = 209,
    difficulty: Difficulty = Difficulty.medium,
    default_template: str | None = "C",
) -> tuple[int, int]:
    """Seed one Topic and one Problem (and optionally a Plan/PlanDay/PlanItem
    scheduling it on TODAY). Returns (topic_id, problem_id).
    """
    with Session(engine) as session:
        topic = Topic(
            code="sliding-window", name="滑动窗口", config_json=config_json, is_active=is_active
        )
        session.add(topic)
        session.commit()
        session.refresh(topic)

        problem = Problem(
            topic_id=topic.id,
            lc_id=lc_id,
            title="长度最小的子数组",
            url="https://leetcode.cn/problems/minimum-size-subarray-sum/",
            difficulty=difficulty,
            section="§2.2",
            section_name="越长越合法",
            default_template=default_template,
        )
        session.add(problem)
        session.commit()
        session.refresh(problem)

        if with_plan:
            plan = Plan(topic_id=topic.id, name="计划", start_date=TODAY)
            session.add(plan)
            session.commit()
            session.refresh(plan)
            day = PlanDay(
                plan_id=plan.id,
                day_index=1,
                planned_date=TODAY,
                phase="阶段一",
                theme="定长窗口三步走",
            )
            session.add(day)
            session.commit()
            session.refresh(day)
            session.add(PlanItem(plan_day_id=day.id, problem_id=problem.id))
            session.commit()
        return topic.id, problem.id


def make_client(
    engine, *, today: date = TODAY, raise_server_exceptions: bool = True
) -> TestClient:
    return TestClient(
        create_app(engine=engine, today_provider=lambda: today),
        raise_server_exceptions=raise_server_exceptions,
    )


@pytest.fixture
def client(engine):
    # Fallback mode (no active plan) -- what every POST /api/attempts test
    # is written against.
    seed(engine, with_plan=False)
    return make_client(engine)
