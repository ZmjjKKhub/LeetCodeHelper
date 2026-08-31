from datetime import date

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from leetcode_helper.models import (
    Attempt,
    AttemptKind,
    Difficulty,
    DurationBucket,
    Mark,
    Plan,
    PlanDay,
    PlanItem,
    Problem,
    Template,
    Topic,
)
from leetcode_helper.web.app_factory import create_app

CONFIG_JSON = (
    '{"code": "sliding-window", "name": "\\u6ed1\\u52a8\\u7a97\\u53e3", '
    '"time_limits": {"easy": 480, "medium": 1200, "hard": 2100}, "card_fields": []}'
)


@pytest.fixture
def engine():
    # StaticPool is required (not just check_same_thread=False): the
    # TestClient dispatches requests on a different thread than the test
    # body, and plain SingletonThreadPool (sqlite's default for ":memory:")
    # hands each thread its own separate in-memory database -- the seeded
    # rows would be invisible to the request. StaticPool shares one
    # connection across threads.
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(engine)
    return engine


def seed(engine, *, with_plan: bool, is_active: bool = True):
    with Session(engine) as session:
        topic = Topic(
            code="sliding-window", name="滑动窗口", config_json=CONFIG_JSON, is_active=is_active
        )
        session.add(topic)
        session.commit()
        session.refresh(topic)

        problem = Problem(
            topic_id=topic.id,
            lc_id=209,
            title="长度最小的子数组",
            url="https://leetcode.cn/problems/minimum-size-subarray-sum/",
            difficulty=Difficulty.medium,
            section="§2.2",
            section_name="越长越合法",
            default_template="C",
        )
        session.add(problem)
        session.commit()
        session.refresh(problem)

        if with_plan:
            plan = Plan(topic_id=topic.id, name="计划", start_date=date(2026, 9, 1))
            session.add(plan)
            session.commit()
            session.refresh(plan)
            day = PlanDay(
                plan_id=plan.id,
                day_index=1,
                planned_date=date(2026, 9, 1),
                phase="阶段一",
                theme="定长窗口三步走",
            )
            session.add(day)
            session.commit()
            session.refresh(day)
            session.add(PlanItem(plan_day_id=day.id, problem_id=problem.id))
            session.commit()
        return topic.id, problem.id


def make_client(engine) -> TestClient:
    return TestClient(create_app(engine=engine, today_provider=lambda: date(2026, 9, 1)))


def test_root_redirects_to_today(engine):
    seed(engine, with_plan=True)
    response = make_client(engine).get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/today"


def test_today_page_renders_planned_items(engine):
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text

    assert "长度最小的子数组" in body
    assert "定长窗口三步走" in body
    assert "20:00" in body  # 1200 秒的限时
    assert "没有排期" not in body


def test_today_page_renders_fallback_when_no_plan_day(engine):
    seed(engine, with_plan=False)
    body = make_client(engine).get("/today").text

    assert "今天没有排期" in body
    assert "长度最小的子数组" in body
    assert "§2.2" in body


def test_today_page_no_active_topic_is_not_a_500(engine):
    # No topic at all -> must not be an unhandled 500 stack trace.
    response = make_client(engine).get("/today")
    assert response.status_code != 500
    assert response.status_code < 500 or response.status_code == 503


def test_inactive_topic_is_skipped(engine):
    seed(engine, with_plan=True, is_active=False)
    response = make_client(engine).get("/today")
    # No active topic exists (the seeded one is inactive), so this must
    # behave the same as "no topic" -- never render the inactive topic's data.
    assert "长度最小的子数组" not in response.text


def test_duration_formatting_for_hard_limit(engine):
    with Session(engine) as session:
        topic = Topic(code="sliding-window", name="滑动窗口", config_json=CONFIG_JSON)
        session.add(topic)
        session.commit()
        session.refresh(topic)
        problem = Problem(
            topic_id=topic.id,
            lc_id=42,
            title="困难题",
            url="https://leetcode.cn/problems/hard/",
            difficulty=Difficulty.hard,
            section="§3.1",
            section_name="困难分组",
        )
        session.add(problem)
        session.commit()

    body = make_client(engine).get("/today").text
    assert "35:00" in body
    # No zero-padding bug: must not render as "350:0" or similar garbage.
    assert "350:0" not in body


def test_done_item_renders_without_form_and_shows_mark(engine):
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=date(2026, 9, 1),
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.within,
                time_limit_sec=1200,
                submit_count=1,
                mark=Mark.A,
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text
    assert "已录入" in body
    assert 'name="duration_bucket"' not in body
    assert "<form" not in body


def test_pending_item_form_defaults_template_and_hx_target(engine):
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(Template(topic_id=topic_id, code="C", name="模板C"))
        session.add(Template(topic_id=topic_id, code="A", name="模板A"))
        session.commit()

    body = make_client(engine).get("/today").text
    assert f'hx-target="#problem-{problem_id}"' in body
    assert f'id="problem-{problem_id}"' in body
    # default_template is "C" for the seeded problem: the <option value="C">
    # inside the template <select> (not the unrelated mark A/B/C radios)
    # must carry `selected`.
    select_start = body.index("<select")
    select_end = body.index("</select>", select_start)
    select_html = body[select_start:select_end]
    idx_c = select_html.index('value="C"')
    snippet = select_html[idx_c : idx_c + 40]
    assert "selected" in snippet


def test_plan_day_with_zero_items_is_empty_state(engine):
    with Session(engine) as session:
        topic = Topic(code="sliding-window", name="滑动窗口", config_json=CONFIG_JSON)
        session.add(topic)
        session.commit()
        session.refresh(topic)
        plan = Plan(topic_id=topic.id, name="计划", start_date=date(2026, 9, 1))
        session.add(plan)
        session.commit()
        session.refresh(plan)
        session.add(
            PlanDay(
                plan_id=plan.id,
                day_index=1,
                planned_date=date(2026, 9, 1),
                phase="阶段一",
                theme="空的一天",
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text
    assert "没有待做的题了" in body


def test_fallback_with_all_attempted_is_empty_state(engine):
    topic_id, problem_id = seed(engine, with_plan=False)
    with Session(engine) as session:
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=date(2026, 9, 1),
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.within,
                time_limit_sec=1200,
                submit_count=1,
                mark=Mark.A,
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text
    assert "没有待做的题了" in body


def test_problem_link_opens_in_new_tab(engine):
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    assert 'target="_blank"' in body


def test_x_cloak_style_present(engine):
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    assert "[x-cloak]" in body
    assert "display: none !important" in body
