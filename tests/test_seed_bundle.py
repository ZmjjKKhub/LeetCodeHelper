from pathlib import Path

import pytest
import yaml

from leetcode_helper.seed.bundle import SeedBundleError, load_bundle

# Repo root, resolved from this file's location rather than the process cwd,
# so this test passes no matter where pytest is invoked from.
REPO_ROOT = Path(__file__).resolve().parent.parent
SHIPPED_SLIDING_WINDOW_DIR = REPO_ROOT / "data" / "topics" / "sliding-window"

TOPIC_YAML = """
code: sliding-window
name: 滑动窗口
time_limits: {easy: 480, medium: 1200, hard: 2100}
card_fields:
  - {key: trigger_feature, label: 触发特征, type: text}
"""

TEMPLATES_YAML = """
- code: C
  name: 不定长·求最短
  language: python
  content: "while ..."
  pitfalls: "别忘了 del cnt[x]"
  trigger_signal: "求最短/最小"
"""

PROBLEMS_YAML = """
- lc_id: 209
  title: 长度最小的子数组
  url: https://leetcode.cn/problems/minimum-size-subarray-sum/
  difficulty: medium
  section: "§2.2"
  section_name: 越长越合法/求最短/最小
  default_template: C
"""

PLAN_YAML = """
name: 滑动窗口 30 天
start_date: 2026-09-01
days:
  - day_index: 1
    phase: 阶段一
    theme: 定长窗口的三步走
    problems: [209]
"""


def _write(tmp_path, *, topic=TOPIC_YAML, templates=TEMPLATES_YAML,
           problems=PROBLEMS_YAML, plan=PLAN_YAML):
    (tmp_path / "topic.yaml").write_text(topic, encoding="utf-8")
    (tmp_path / "templates.yaml").write_text(templates, encoding="utf-8")
    (tmp_path / "problems.yaml").write_text(problems, encoding="utf-8")
    (tmp_path / "plan_default.yaml").write_text(plan, encoding="utf-8")
    return tmp_path


def test_load_valid_bundle(tmp_path):
    bundle = load_bundle(_write(tmp_path))
    assert bundle.config.code == "sliding-window"
    assert len(bundle.problems) == 1
    assert bundle.problems[0].lc_id == 209
    assert bundle.plan.days[0].problem_lc_ids == (209,)


def test_duplicate_lc_id_rejected(tmp_path):
    problems = PROBLEMS_YAML + PROBLEMS_YAML
    with pytest.raises(SeedBundleError, match="lc_id 重复: 209"):
        load_bundle(_write(tmp_path, problems=problems))


def test_empty_section_rejected(tmp_path):
    problems = PROBLEMS_YAML.replace('section: "§2.2"', 'section: ""')
    with pytest.raises(SeedBundleError, match="lc_id=209 的 section 不能为空"):
        load_bundle(_write(tmp_path, problems=problems))


def test_bad_difficulty_rejected(tmp_path):
    problems = PROBLEMS_YAML.replace("difficulty: medium", "difficulty: 1800")
    with pytest.raises(SeedBundleError, match="lc_id=209 的 difficulty 非法: 1800"):
        load_bundle(_write(tmp_path, problems=problems))


def test_unknown_default_template_rejected(tmp_path):
    problems = PROBLEMS_YAML.replace("default_template: C", "default_template: Z")
    with pytest.raises(SeedBundleError, match="lc_id=209 的 default_template=Z 不存在"):
        load_bundle(_write(tmp_path, problems=problems))


def test_plan_referencing_unknown_problem_rejected(tmp_path):
    plan = PLAN_YAML.replace("problems: [209]", "problems: [209, 76]")
    with pytest.raises(SeedBundleError, match="plan_default.yaml 第 1 天引用了不存在的 lc_id: 76"):
        load_bundle(_write(tmp_path, plan=plan))


def test_duplicate_day_index_rejected(tmp_path):
    plan = yaml.safe_load(PLAN_YAML)
    plan["days"].append(dict(plan["days"][0]))
    with pytest.raises(SeedBundleError, match="plan_default.yaml 的 day_index 重复: 1"):
        load_bundle(_write(tmp_path, plan=yaml.safe_dump(plan, allow_unicode=True)))


def test_invalid_topic_config_surfaces_as_bundle_error(tmp_path):
    topic = TOPIC_YAML.replace("hard: 2100", "hard: 0")
    with pytest.raises(SeedBundleError, match="time_limits.hard 必须是正整数"):
        load_bundle(_write(tmp_path, topic=topic))


def test_missing_topic_file_rejected(tmp_path):
    _write(tmp_path)
    (tmp_path / "topic.yaml").unlink()
    with pytest.raises(SeedBundleError, match="缺少文件: topic.yaml"):
        load_bundle(tmp_path)


def test_topic_yaml_non_dict_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match=r"topic\.yaml 的顶层必须是 dict，实际是 NoneType"):
        load_bundle(_write(tmp_path, topic=""))


def test_problems_yaml_non_list_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match=r"problems\.yaml 的顶层必须是 list，实际是 dict"):
        load_bundle(_write(tmp_path, problems="a: 1\nb: 2\n"))


def test_templates_yaml_non_list_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match=r"templates\.yaml 的顶层必须是 list，实际是 dict"):
        load_bundle(_write(tmp_path, templates="a: 1\n"))


def test_plan_yaml_non_dict_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match=r"plan_default\.yaml 的顶层必须是 dict，实际是 list"):
        load_bundle(_write(tmp_path, plan="- 1\n"))


def test_problems_entry_not_mapping_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match="problems.yaml 里有条目不是合法的映射"):
        load_bundle(_write(tmp_path, problems="- 209\n"))


def test_templates_entry_not_mapping_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match="templates.yaml 里有条目不是合法的映射"):
        load_bundle(_write(tmp_path, templates="- C\n"))


def test_plan_day_entry_not_mapping_rejected(tmp_path):
    plan = "name: p\nstart_date: 2026-09-01\ndays: [1]\n"
    with pytest.raises(SeedBundleError, match="days 里有条目不是合法的映射"):
        load_bundle(_write(tmp_path, plan=plan))


def test_day_problems_scalar_rejected(tmp_path):
    plan = PLAN_YAML.replace("problems: [209]", "problems: 209")
    with pytest.raises(SeedBundleError, match="problems 必须是列表"):
        load_bundle(_write(tmp_path, plan=plan))


def test_empty_problems_rejected(tmp_path):
    with pytest.raises(SeedBundleError, match="problems.yaml 不能为空"):
        load_bundle(_write(tmp_path, problems="[]\n"))


def test_empty_plan_days_rejected(tmp_path):
    plan = "name: p\nstart_date: 2026-09-01\ndays: []\n"
    with pytest.raises(SeedBundleError, match="days 不能为空"):
        load_bundle(_write(tmp_path, plan=plan))


def test_empty_templates_allowed(tmp_path):
    problems = PROBLEMS_YAML.replace("  default_template: C\n", "\n")
    bundle = load_bundle(_write(tmp_path, templates="[]\n", problems=problems))
    assert bundle.templates == ()


def test_duplicate_template_code_rejected(tmp_path):
    templates = TEMPLATES_YAML + TEMPLATES_YAML
    with pytest.raises(SeedBundleError, match="templates.yaml 的 code 重复: C"):
        load_bundle(_write(tmp_path, templates=templates))


def test_template_missing_code_rejected(tmp_path):
    templates = """
- name: 无code模板
  language: python
  content: "..."
  pitfalls: "..."
  trigger_signal: "..."
"""
    with pytest.raises(SeedBundleError, match="templates.yaml 里有条目缺少 code"):
        load_bundle(_write(tmp_path, templates=templates))


def test_lc_id_bool_rejected(tmp_path):
    problems = PROBLEMS_YAML.replace("lc_id: 209", "lc_id: true")
    with pytest.raises(SeedBundleError, match="lc_id 非法: True"):
        load_bundle(_write(tmp_path, problems=problems))


def test_day_index_bool_rejected(tmp_path):
    plan = PLAN_YAML.replace("day_index: 1", "day_index: true")
    with pytest.raises(SeedBundleError, match="day_index 非法: True"):
        load_bundle(_write(tmp_path, plan=plan))


def test_start_date_datetime_rejected(tmp_path):
    plan = PLAN_YAML.replace("start_date: 2026-09-01", "start_date: 2026-09-01 10:00:00")
    with pytest.raises(SeedBundleError, match="start_date 非法"):
        load_bundle(_write(tmp_path, plan=plan))


@pytest.mark.parametrize(
    "kwargs",
    [
        {"topic": ""},
        {"problems": "a: 1\nb: 2\n"},
        {"templates": "a: 1\n"},
        {"problems": "- 209\n"},
        {"plan": "name: p\nstart_date: 2026-09-01\ndays: [1]\n"},
        {"plan": PLAN_YAML.replace("problems: [209]", "problems: 209")},
    ],
)
def test_malformed_yaml_shape_raises_seed_bundle_error(tmp_path, kwargs):
    with pytest.raises(SeedBundleError):
        load_bundle(_write(tmp_path, **kwargs))


def test_shipped_sliding_window_bundle_is_valid():
    # The real bundle a day-one user imports (`uv run python -m
    # leetcode_helper.seed data/topics/sliding-window`) -- every other test
    # in this file exercises load_bundle against synthetic YAML in tmp_path,
    # so nothing ever loaded the shipped files themselves. A typo in a
    # default_template, or plan_default.yaml referencing a dropped lc_id,
    # would only be caught here instead of by a real user hitting it.
    bundle = load_bundle(SHIPPED_SLIDING_WINDOW_DIR)

    assert len(bundle.problems) == 15

    # Cross-check that matters for Phase 1.5, when the remaining problems
    # and the 30-day plan get appended: the plan's problem references and
    # the problem set must line up exactly, with nothing on either side
    # left orphaned.
    plan_lc_ids = {lc_id for day in bundle.plan.days for lc_id in day.problem_lc_ids}
    problem_lc_ids = {p.lc_id for p in bundle.problems}
    assert plan_lc_ids == problem_lc_ids

    # Every default_template must resolve to a template that actually
    # exists in templates.yaml (load_bundle already enforces this while
    # parsing, but assert it explicitly here so the intent is visible).
    template_codes = {t.code for t in bundle.templates}
    for problem in bundle.problems:
        if problem.default_template is not None:
            assert problem.default_template in template_codes

    # No duplicate lc_ids, no empty titles/urls/sections -- a quality bar
    # a synthetic test bundle wouldn't catch but a shipped one should meet.
    assert len(problem_lc_ids) == len(bundle.problems)
    for problem in bundle.problems:
        assert problem.title
        assert problem.url
        assert problem.section


def test_shipped_sliding_window_sections_match_the_source_list():
    """小节划分必须与灵神题单原文一致。

    https://leetcode.cn/discuss/post/3578981/ 的「一、定长滑动窗口」下：
      §1.1 基础        1456, 643, 1343, 2090, 2379, 2841, 2461, 1423
      §1.2 进阶（选做） 1052, 2134, 567, 438, 30, 1888（其下「思维扩展」含 2653）

    这条断言存在的原因：section 决定 P7 热力图的分组和 R5「某 section 的 C 类题
    占比 > 50%」规则，而它无法从 LeetCode 官方接口取得——只能照抄题单。1052 曾
    被错放进 §1.1，正是这类错误没有断言看着才会发生。
    """
    bundle = load_bundle(SHIPPED_SLIDING_WINDOW_DIR)
    by_section: dict[str, set[int]] = {}
    for problem in bundle.problems:
        by_section.setdefault(problem.section, set()).add(problem.lc_id)

    assert by_section == {
        "§1.1": {1456, 643, 1343, 2090, 2379, 2841, 2461, 1423},
        "§1.2": {1052, 2134, 567, 438, 30, 1888, 2653},
    }

    # §1.2 的标题就是「进阶（选做）」，所以那一组必须是选做题。
    # 规格 R5 有一条建议依赖 is_optional：「周 C 类占比 < 10% 且模板默写连续
    # 2 周满分 → 加入本阶段的选做/进阶题」。全 false 会让那条规则永不触发。
    optional = {p.lc_id for p in bundle.problems if p.is_optional}
    assert optional == by_section["§1.2"]
    assert not (optional & by_section["§1.1"])
