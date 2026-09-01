from datetime import date

from sqlmodel import Session

from leetcode_helper.models import (
    Attempt,
    AttemptKind,
    Difficulty,
    DurationBucket,
    Mark,
    Plan,
    PlanDay,
    Problem,
    Template,
    Topic,
)
from tests.conftest import CONFIG_JSON, make_client, seed


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


def test_today_page_no_active_topic_is_a_503(engine):
    # No topic at all -> the "no active topic, probably forgot to seed" page,
    # never an unhandled 500 stack trace.
    response = make_client(engine).get("/today")
    assert response.status_code == 503


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


def test_done_item_shows_mark_and_a_reachable_correction_control(engine):
    # C1: a recorded attempt must stay correctable -- a done row keeps a 修改
    # control (not just the bare "已录入" label) that reopens the same form.
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
    assert "修改" in body
    # 录入 (the "not started yet" label) must not also be present on a done row.
    assert "录入</a>" not in body


def test_done_item_form_is_prefilled_with_recorded_values(engine):
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(Template(topic_id=topic_id, code="C", name="模板C"))
        session.add(Template(topic_id=topic_id, code="A", name="模板A"))
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=date(2026, 9, 1),
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.over,
                time_limit_sec=1200,
                submit_count=4,
                mark=Mark.B,
                used_template="A",
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text

    # The recorded duration_bucket radio is checked.
    assert 'value="over" ' in body and "checked" in body
    over_start = body.index('value="over"')
    over_end = body.index("</label>", over_start)
    assert "checked" in body[over_start:over_end]

    # The recorded used_template ("A") is selected in the <select>.
    select_start = body.index("<select")
    select_end = body.index("</select>", select_start)
    select_html = body[select_start:select_end]
    idx_a = select_html.index('value="A"')
    assert "selected" in select_html[idx_a : idx_a + 40]

    # The recorded mark (B) is indicated as currently selected.
    b_start = body.index('name="mark" value="B"')
    b_end = body.index("</button>", b_start)
    assert 'aria-pressed="true"' in body[b_start:b_end]

    # The recorded submit_count (4) prefills the field.
    assert 'name="submit_count" value="4"' in body


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
    # inside the template <select> (not the unrelated mark A/B/C buttons)
    # must carry `selected`.
    select_start = body.index("<select")
    select_end = body.index("</select>", select_start)
    select_html = body[select_start:select_end]
    idx_c = select_html.index('value="C"')
    snippet = select_html[idx_c : idx_c + 40]
    assert "selected" in snippet


def test_mark_buttons_submit_directly_no_separate_save_button(engine):
    # The product hypothesis this whole phase exists to test is <=20s and
    # <=3 clicks: 录入(open) -> 用时(duration) -> 标记(mark). That only works
    # if clicking a mark button *is* the submit action -- collapsing 标记
    # and 保存 into one click -- rather than a fourth separate "保存" button.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text

    assert '<button type="submit" name="mark" value="A">A</button>' in body
    assert '<button type="submit" name="mark" value="B">B</button>' in body
    assert '<button type="submit" name="mark" value="C">C</button>' in body
    assert "保存" not in body
    # duration_bucket must still be required client-side so an incomplete
    # submission is caught by the browser instead of round-tripping.
    assert 'name="duration_bucket" value="within" required' in body


def test_form_has_disabled_elt_for_double_submit_guard(engine):
    # I6: hx-disabled-elt gives "it's saving" feedback and prevents a
    # double-click from writing two Attempt rows.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    assert 'hx-disabled-elt="find button"' in body


def test_submit_count_field_comes_after_mark_buttons(engine):
    # submit_count is the least-used field; it must not sit first in tab/
    # visual order ahead of duration and mark.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    mark_button_index = body.index('name="mark" value="A"')
    submit_count_index = body.index('name="submit_count"')
    assert mark_button_index < submit_count_index


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
    # This plan day genuinely has no problems scheduled -- distinct from
    # "nothing left to practice at all" (the fallback case below), which
    # points the user at re-importing instead.
    assert "今天的排期没有安排题目" in body
    assert "uv run python -m leetcode_helper.seed" not in body


def test_fallback_with_all_attempted_is_empty_state(engine):
    # Attempted on an *earlier* date, not today -- a problem attempted today
    # must still show up in the fallback list (as a done row, see
    # test_fallback_shows_todays_attempt_as_done_row below), so this test's
    # "nothing left" state has to be earned with an older attempt.
    topic_id, problem_id = seed(engine, with_plan=False)
    with Session(engine) as session:
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=date(2026, 8, 20),
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
    # The fallback empty state means nothing is left to practice at all --
    # give the user the exact command to re-import after adding more
    # problems, instead of a dead end.
    assert "uv run python -m leetcode_helper.seed data/topics/sliding-window" in body


def test_fallback_shows_todays_attempt_as_done_row(engine):
    # C1: a problem attempted today must not vanish from the fallback list
    # on reload -- it must still render, as a done row that can be
    # corrected, not silently disappear.
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
    assert "没有待做的题了" not in body
    assert "长度最小的子数组" in body
    assert "已录入" in body


def test_problem_link_opens_in_new_tab(engine):
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    assert 'target="_blank"' in body


def test_unrelated_keyerror_is_500_not_disguised_as_no_active_topic(engine, monkeypatch):
    # C1: the old handler was registered on the bare LookupError, which is
    # also the base class of KeyError and IndexError. An internal bug (e.g.
    # a raw dict subscript somewhere in the request) would get silently
    # relabeled as "you forgot to seed" (503) with its traceback destroyed,
    # instead of surfacing as the 500 it actually is.
    seed(engine, with_plan=True)

    import leetcode_helper.web.routes.today as today_routes

    def boom(*args, **kwargs):
        raise KeyError("some unrelated bug")

    monkeypatch.setattr(today_routes, "get_today_view", boom)

    response = make_client(engine, raise_server_exceptions=False).get("/today")
    assert response.status_code == 500
    assert response.status_code != 503
