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

    # duration_bucket=over/mark=B is the "over" outcome -- its button is
    # marked as currently selected.
    over_start = body.index('name="outcome" value="over"')
    over_end = body.index("</button>", over_start)
    assert 'aria-pressed="true"' in body[over_start:over_end]

    # The recorded used_template ("A") is selected in the <select>.
    select_start = body.index("<select")
    select_end = body.index("</select>", select_start)
    select_html = body[select_start:select_end]
    idx_a = select_html.index('value="A"')
    assert "selected" in select_html[idx_a : idx_a + 40]

    # No *other* outcome button is marked current.
    for other in ("within_solid", "within_shaky", "unsolved"):
        other_start = body.index(f'name="outcome" value="{other}"')
        other_end = body.index("</button>", other_start)
        assert 'aria-pressed="true"' not in body[other_start:other_end]

    # The recorded submit_count (4) seeds the Alpine `count` state.
    assert "count: 4" in body


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


def test_outcome_buttons_submit_directly_no_separate_save_button(engine):
    # The product hypothesis this whole phase exists to test is <=20s and
    # <=2 clicks: 录入(open) -> 今天做得怎么样(outcome). That only works if
    # clicking an outcome button *is* the submit action -- collapsing the
    # choice and 保存 into one click -- rather than a separate "保存" button.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text

    assert '<button type="submit" name="outcome" value="within_solid"' in body
    assert '<button type="submit" name="outcome" value="within_shaky"' in body
    assert '<button type="submit" name="outcome" value="over"' in body
    assert '<button type="submit" name="outcome" value="unsolved"' in body
    # "保存" now legitimately appears as prose ("点一下即保存") explaining
    # that an outcome click *is* the save -- but there must be no standalone
    # <button>保存</button>-style separate save control.
    assert ">保存<" not in body


def test_form_has_disabled_elt_for_double_submit_guard(engine):
    # I6: hx-disabled-elt gives "it's saving" feedback and prevents a
    # double-click from writing two Attempt rows.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    assert 'hx-disabled-elt="find button"' in body


def test_submit_count_and_template_come_before_outcome_buttons(engine):
    # C2: submit_count and used_template must be visible and reachable
    # *before* the outcome buttons, since clicking an outcome button submits
    # the form -- the interaction is over the moment that happens. They are
    # rendered earlier in DOM order, on purpose, so both tab order and
    # "clickable before submit" hold with no CSS reordering involved.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    submit_count_index = body.index('name="submit_count"')
    template_select_index = body.index('name="used_template"')
    outcome_button_index = body.index('name="outcome" value="within_solid"')
    assert submit_count_index < outcome_button_index
    assert template_select_index < outcome_button_index


def test_stepper_buttons_are_type_button_not_submit(engine):
    # The [-]/[+] steppers must never submit the form themselves -- only the
    # outcome buttons (type="submit") do.
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    stepper_start = body.index('class="stepper"')
    stepper_end = body.index("</div>", stepper_start)
    stepper_html = body[stepper_start:stepper_end]
    assert stepper_html.count('type="button"') == 2
    assert 'type="submit"' not in stepper_html

    assert '<button type="submit" name="outcome" value="within_solid"' in body
    assert '<button type="submit" name="outcome" value="within_shaky"' in body
    assert '<button type="submit" name="outcome" value="over"' in body
    assert '<button type="submit" name="outcome" value="unsolved"' in body


def test_submit_count_defaults_to_one_and_min_is_one(engine):
    seed(engine, with_plan=True)
    body = make_client(engine).get("/today").text
    assert "count: 1" in body
    assert "Math.max(1, count - 1)" in body


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


def test_entry_panel_controls_have_visible_labels(engine):
    # The panel used to be four unlabeled controls (a bare radio group, a
    # dropdown of bare template codes, a "[-] 1 [+]" stepper, and bare A/B/C
    # buttons) -- every one of them now needs a visible label/legend saying
    # what it is. The 用时/掌握程度 pair has since been merged into one
    # 今天做得怎么样 control (see split_outcome in services/attempts.py).
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(Template(topic_id=topic_id, code="A", name="定长滑窗", trigger_signal="窗口长度固定"))
        session.commit()

    body = make_client(engine).get("/today").text
    assert "用了哪个模板" in body
    assert "提交次数" in body
    assert "今天做得怎么样？（点一下即保存）" in body
    # The consequence line making the commit explicit.
    assert "点一下即保存" in body


def test_template_dropdown_shows_code_name_and_trigger_signal_title(engine):
    # C2: repositories/today.py::list_template_codes used to throw away
    # `name`/`trigger_signal`, leaving the user with a dropdown of bare
    # letters and no way to tell what any of them mean.
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(
            Template(
                topic_id=topic_id,
                code="A",
                name="定长滑窗（入 → 更新 → 出）",
                trigger_signal="窗口长度固定",
            )
        )
        session.commit()

    # Fresh row.
    body = make_client(engine).get("/today").text
    assert "A · 定长滑窗（入 → 更新 → 出）" in body
    assert 'title="窗口长度固定"' in body

    # Done row (via /attempts response, and via a subsequent GET /today).
    client = make_client(engine)
    post_body = client.post(
        "/attempts",
        data={
            "problem_id": problem_id,
            "outcome": "within_solid",
            "submit_count": "1",
            "used_template": "A",
        },
    ).text
    assert "A · 定长滑窗（入 → 更新 → 出）" in post_body
    assert 'title="窗口长度固定"' in post_body

    get_body = client.get("/today").text
    assert "A · 定长滑窗（入 → 更新 → 出）" in get_body
    assert 'title="窗口长度固定"' in get_body


def test_done_row_summary_uses_outcome_label(engine):
    # The done-row summary now reads the merged outcome's own Chinese label
    # ("已录入：限时内做出来，思路清楚") rather than the old raw "A / 限时内"
    # mark+bucket rendering.
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
    assert "已录入：限时内做出来，思路清楚" in body
    assert "已录入：A / within" not in body
    assert "已录入：A / 限时内" not in body


def test_done_row_with_unreachable_combo_renders_without_crashing_and_marks_none_current(engine):
    # (within, C) -- 限时内做出来 but marked C -- cannot be produced by the
    # new four-option UI (within only ever pairs with A or B here), but an
    # older row or a direct write can still have it. outcome_of must return
    # None for it, the template must fall back to the old raw mark/bucket
    # summary instead of guessing, and no outcome button may render as
    # current.
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
                mark=Mark.C,
            )
        )
        session.commit()

    response = make_client(engine).get("/today")
    assert response.status_code == 200
    body = response.text
    # Falls back to the raw mark + Chinese bucket-label rendering.
    assert "已录入：C / 限时内" in body

    for value in ("within_solid", "within_shaky", "over", "unsolved"):
        start = body.index(f'name="outcome" value="{value}"')
        end = body.index("</button>", start)
        assert 'aria-pressed="true"' not in body[start:end]
        assert 'class="current"' not in body[start:end]


def test_attempts_response_renders_labelled_panel_with_real_templates(engine):
    # C2: create_attempt's own re-render used to pass template_codes=[] --
    # this is the path that regression covers, now against the real,
    # labelled option list (code · name), not an empty <select>.
    topic_id, problem_id = seed(engine, with_plan=True)
    with Session(engine) as session:
        session.add(Template(topic_id=topic_id, code="A", name="定长滑窗", trigger_signal="窗口固定"))
        session.add(Template(topic_id=topic_id, code="B", name="不定长滑窗", trigger_signal="窗口可变"))
        session.commit()

    body = make_client(engine).post(
        "/attempts",
        data={
            "problem_id": problem_id,
            "outcome": "within_solid",
            "submit_count": "1",
            "used_template": "B",
        },
    ).text

    assert "用了哪个模板" in body
    assert "A · 定长滑窗" in body
    assert "B · 不定长滑窗" in body
    assert 'title="窗口固定"' in body
    assert 'title="窗口可变"' in body
    select_start = body.index("<select")
    select_end = body.index("</select>", select_start)
    select_html = body[select_start:select_end]
    idx_b = select_html.index('value="B"')
    assert "selected" in select_html[idx_b : idx_b + 60]


def test_template_shown_as_readout_text_with_hidden_select_behind_correction_toggle(engine):
    # The complaint this change exists to fix: the panel must not present the
    # template as a decision the user has to make. The system already judges
    # it (Problem.default_template, now derived from the 题单 section) --
    # this renders that judgment as text, with 改 revealing the underlying
    # <select> (still there, still `used_template`, same options) only on
    # demand.
    topic_id, problem_id = seed(engine, with_plan=True, default_template="A")
    with Session(engine) as session:
        session.add(
            Template(
                topic_id=topic_id,
                code="A",
                name="定长滑窗（入 → 更新 → 出）",
                trigger_signal="窗口长度固定",
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text
    readout_start = body.index('class="template-readout"')
    readout_end = body.index("</p>", readout_start)
    readout_html = body[readout_start:readout_end]

    # The judged template renders as text, not a forced choice.
    assert "A · 定长滑窗（入 → 更新 → 出）" in readout_html
    assert "改" in readout_html
    assert 'x-show="!editTemplate"' in body

    # The <select> is still present in the DOM (so 改 can reveal it and the
    # correction path keeps working), but it is gated behind the same
    # row-local Alpine state as the readout -- hidden until 改 is clicked.
    select_start = body.index("<select", readout_end)
    select_tag_end = body.index(">", select_start)
    select_tag = body[select_start:select_tag_end]
    assert 'name="used_template"' in select_tag
    assert 'x-show="editTemplate"' in select_tag


def test_done_row_shows_recorded_template_not_derived_default(engine):
    # C1/R6: a corrected row must show what was actually recorded, not the
    # derived default -- and since they differ here, the gap itself (the
    # signal R6 exists to capture) must be visible too.
    topic_id, problem_id = seed(engine, with_plan=True, default_template="C")
    with Session(engine) as session:
        session.add(Template(topic_id=topic_id, code="A", name="定长滑窗", trigger_signal="窗口固定"))
        session.add(Template(topic_id=topic_id, code="C", name="不定长·求最短", trigger_signal="求最短"))
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=date(2026, 9, 1),
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.within,
                time_limit_sec=1200,
                submit_count=1,
                mark=Mark.A,
                used_template="A",
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text
    readout_start = body.index('class="template-readout"')
    readout_end = body.index("</p>", readout_start)
    readout_html = body[readout_start:readout_end]

    # Recorded ("A"), not derived ("C"), is the headline.
    assert "A · 定长滑窗" in readout_html
    # But the derived expectation the user diverged from is visible too.
    assert "原本预期 C" in readout_html


def test_row_with_no_derived_template_reads_wu_and_stays_correctable(engine):
    topic_id, problem_id = seed(engine, with_plan=True, default_template=None)
    body = make_client(engine).get("/today").text
    readout_start = body.index('class="template-readout"')
    readout_end = body.index("</p>", readout_start)
    readout_html = body[readout_start:readout_end]
    assert "无" in readout_html
    assert "改" in readout_html


def test_matching_recorded_template_shows_no_mismatch_note(engine):
    topic_id, problem_id = seed(engine, with_plan=True, default_template="A")
    with Session(engine) as session:
        session.add(Template(topic_id=topic_id, code="A", name="定长滑窗", trigger_signal="窗口固定"))
        session.add(
            Attempt(
                problem_id=problem_id,
                attempt_date=date(2026, 9, 1),
                kind=AttemptKind.new,
                duration_bucket=DurationBucket.within,
                time_limit_sec=1200,
                submit_count=1,
                mark=Mark.A,
                used_template="A",
            )
        )
        session.commit()

    body = make_client(engine).get("/today").text
    readout_start = body.index('class="template-readout"')
    readout_end = body.index("</p>", readout_start)
    readout_html = body[readout_start:readout_end]
    assert "原本预期" not in readout_html


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
