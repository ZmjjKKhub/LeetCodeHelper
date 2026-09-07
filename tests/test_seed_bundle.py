from pathlib import Path

import pytest
import yaml

from leetcode_helper.seed.bundle import SeedBundleError, load_bundle
from leetcode_helper.services.topics import resolve_section_template

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

TOPIC_YAML_WITH_SECTION_TEMPLATES = """
code: sliding-window
name: 滑动窗口
time_limits: {easy: 480, medium: 1200, hard: 2100}
card_fields:
  - {key: trigger_feature, label: 触发特征, type: text}
section_templates:
  "§1": A
  "§2.2": C
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


# --- section_templates: derive default_template from the 题单 section ---

TEMPLATES_A_AND_C_YAML = """
- code: A
  name: 定长滑窗
  language: python
  content: "..."
  pitfalls: "..."
  trigger_signal: "定长"
- code: C
  name: 不定长·求最短
  language: python
  content: "while ..."
  pitfalls: "别忘了 del cnt[x]"
  trigger_signal: "求最短/最小"
"""

PROBLEMS_NO_OVERRIDE_YAML = """
- lc_id: 209
  title: 长度最小的子数组
  url: https://leetcode.cn/problems/minimum-size-subarray-sum/
  difficulty: medium
  section: "§2.2"
  section_name: 越长越合法/求最短/最小
- lc_id: 1456
  title: 定长子串中元音的最大数目
  url: https://leetcode.cn/problems/maximum-number-of-vowels-in-a-substring-of-given-length/
  difficulty: medium
  section: "§1.1"
  section_name: 定长滑动窗口 · 基础
"""

PLAN_TWO_PROBLEMS_YAML = """
name: 滑动窗口 30 天
start_date: 2026-09-01
days:
  - day_index: 1
    phase: 阶段一
    theme: 定长窗口的三步走
    problems: [209, 1456]
"""


def test_default_template_derived_from_section_templates(tmp_path):
    bundle = load_bundle(
        _write(
            tmp_path,
            topic=TOPIC_YAML_WITH_SECTION_TEMPLATES,
            templates=TEMPLATES_A_AND_C_YAML,
            problems=PROBLEMS_NO_OVERRIDE_YAML,
            plan=PLAN_TWO_PROBLEMS_YAML,
        )
    )
    by_lc_id = {p.lc_id: p for p in bundle.problems}
    # §2.2 matches the "§2.2" key exactly -> C.
    assert by_lc_id[209].default_template == "C"
    # §1.1 has no exact key, falls back to the "§1" prefix -> A.
    assert by_lc_id[1456].default_template == "A"


def test_per_problem_default_template_overrides_derived_value(tmp_path):
    # lc_id 209 is in §2.2 (derives to C via section_templates), but the
    # problem entry explicitly overrides it to A -- the override must win.
    problems = PROBLEMS_NO_OVERRIDE_YAML.replace(
        'section_name: 越长越合法/求最短/最小\n',
        'section_name: 越长越合法/求最短/最小\n  default_template: A\n',
    )
    bundle = load_bundle(
        _write(
            tmp_path,
            topic=TOPIC_YAML_WITH_SECTION_TEMPLATES,
            templates=TEMPLATES_A_AND_C_YAML,
            problems=problems,
            plan=PLAN_TWO_PROBLEMS_YAML,
        )
    )
    by_lc_id = {p.lc_id: p for p in bundle.problems}
    assert by_lc_id[209].default_template == "A"


def test_section_with_no_matching_key_resolves_to_none(tmp_path):
    problems = """
- lc_id: 1
  title: 无匹配小节
  url: https://leetcode.cn/problems/x/
  difficulty: medium
  section: "§9.9"
  section_name: 不在 section_templates 里
"""
    plan = """
name: p
start_date: 2026-09-01
days:
  - day_index: 1
    phase: 阶段一
    theme: t
    problems: [1]
"""
    bundle = load_bundle(
        _write(
            tmp_path,
            topic=TOPIC_YAML_WITH_SECTION_TEMPLATES,
            templates=TEMPLATES_A_AND_C_YAML,
            problems=problems,
            plan=plan,
        )
    )
    assert bundle.problems[0].default_template is None


def test_section_templates_naming_unknown_template_rejected(tmp_path):
    # section_templates points "§1" at a template code ("Z") that doesn't
    # exist in templates.yaml -- must be rejected the same way an unknown
    # per-problem default_template is.
    topic = TOPIC_YAML_WITH_SECTION_TEMPLATES.replace('"§1": A', '"§1": Z')
    with pytest.raises(
        SeedBundleError, match=r"section_templates\.§1=Z 不存在于 templates\.yaml"
    ):
        load_bundle(
            _write(
                tmp_path,
                topic=topic,
                templates=TEMPLATES_A_AND_C_YAML,
                problems=PROBLEMS_NO_OVERRIDE_YAML,
                plan=PLAN_TWO_PROBLEMS_YAML,
            )
        )


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

    # 223 = 灵神题单的非会员题总数（scripts/build_sliding_window_catalogue.py
    # 生成时报告过的数字）。会员题被那个脚本整个丢弃，所以这里不应该有任何
    # is_premium=True 的条目。
    assert len(bundle.problems) == 223
    assert not any(p.is_premium for p in bundle.problems)

    # Cross-check that matters for import: the plan's problem references and
    # the problem set must line up exactly, with nothing on either side
    # left orphaned.
    plan_lc_ids = {lc_id for day in bundle.plan.days for lc_id in day.problem_lc_ids}
    problem_lc_ids = {p.lc_id for p in bundle.problems}
    assert plan_lc_ids <= problem_lc_ids

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


def test_shipped_sliding_window_plan_covers_every_non_optional_problem_once():
    """plan_default.yaml：35 天、172 道题，题题都在 problems.yaml 里存在、
    题题都不是选做题，且每题只排一次——这三条是 seed/importer.py 增量 upsert
    逻辑能安全工作的前提，被排期两次的题会在导入时产生两个 PlanItem 撞
    UniqueConstraint("plan_day_id", "problem_id")（同一天两次)或被悄悄去重
    （不同天两次），两种结果都不是我们想要的。

    172 = 223 题减去 51 道选做题；5 题/天，最后一天只有 2 题，共 35 天。
    """
    bundle = load_bundle(SHIPPED_SLIDING_WINDOW_DIR)

    assert len(bundle.plan.days) == 35

    plan_lc_ids = [lc_id for day in bundle.plan.days for lc_id in day.problem_lc_ids]
    assert len(plan_lc_ids) == 172
    assert len(set(plan_lc_ids)) == 172  # 不重复排期

    by_lc_id = {p.lc_id: p for p in bundle.problems}
    for lc_id in plan_lc_ids:
        assert lc_id in by_lc_id  # 每个排期引用的题都真的存在
        assert by_lc_id[lc_id].is_optional is False  # 选做题不进排期

    # 反过来也要成立：所有非选做题都被排进了计划里，一个都不漏。
    non_optional_lc_ids = {p.lc_id for p in bundle.problems if not p.is_optional}
    assert set(plan_lc_ids) == non_optional_lc_ids


def test_shipped_sliding_window_sections_match_the_expected_set():
    """小节划分必须与 scripts/build_sliding_window_catalogue.py 解析灵神题单
    原文（https://leetcode.cn/discuss/post/3578981/）得到的结果一致：六个大
    节、十六个 "§X.Y" 编号（"五、三指针"/"六、分组循环" 正文没有编号，脚本
    兜底成 "§5"/"§6"），且每个 section 内的 total/optional 数目固定。

    §2.1 (28/18) 和 §2.3 (18/2) 这两行精确钉住了 "####" 四级标题的作用域
    规则：§2.1 下 "#### §2.1.2 进阶（选做）" 必须让它底下 18 题（不是 0 题）
    is_optional=True；§2.3 下 "#### §2.3.1" 里那条
    "**思维扩展（选做）**" 只能覆盖它之后、下一个 "#### §2.3.2" 之前的 2 题
    （3134/3261），不能一路蔓延到 §2.3.2/§2.3.3 把 1358/2962/.../3859 这些
    核心的"求子数组个数"题也带成选做——这正是曾经出现过的回归（作用域没有
    在新 "#### " 上正确清空导致 §2.1 变成 0 题选做、§2.3 变成 14 题选做）。

    这条断言存在的原因：section 决定 P7 热力图的分组和 R5「某 section 的 C 类
    题占比 > 50%」规则，而它无法从 LeetCode 官方接口取得——只能照抄题单，抄错
    了也没有类型系统能发现。
    """
    bundle = load_bundle(SHIPPED_SLIDING_WINDOW_DIR)

    counts: dict[str, dict[str, int]] = {}
    for problem in bundle.problems:
        c = counts.setdefault(problem.section, {"total": 0, "optional": 0})
        c["total"] += 1
        if problem.is_optional:
            c["optional"] += 1

    assert counts == {
        "§1.1": {"total": 8, "optional": 0},
        "§1.2": {"total": 18, "optional": 18},
        "§2.1": {"total": 28, "optional": 18},
        "§2.2": {"total": 7, "optional": 0},
        "§2.3": {"total": 18, "optional": 2},
        "§2.4": {"total": 5, "optional": 5},
        "§3.1": {"total": 12, "optional": 0},
        "§3.2": {"total": 26, "optional": 2},
        "§3.3": {"total": 7, "optional": 0},
        "§3.4": {"total": 2, "optional": 0},
        "§3.5": {"total": 17, "optional": 5},
        "§3.6": {"total": 2, "optional": 0},
        "§4.1": {"total": 15, "optional": 0},
        "§4.2": {"total": 10, "optional": 0},
        "§5": {"total": 5, "optional": 1},
        "§6": {"total": 43, "optional": 0},
    }

    # §2.1.2 (2730 等 18 题) 必须落在 §2.1 这个 section code 下，不是自成
    # "§2.1.2"——"####" 只影响 is_optional，不产生新的 section。
    by_lc_id = {p.lc_id: p for p in bundle.problems}
    for lc_id in (2730, 2779, 1658, 1838, 2516, 2831, 2271, 2106, 2555, 2009):
        assert by_lc_id[lc_id].section == "§2.1"
        assert by_lc_id[lc_id].is_optional is True

    # §2.3.2/§2.3.3 的核心题必须是非选做——正是曾经被 "####" 作用域 bug
    # 错误吞掉选做状态的那批题。
    for lc_id in (1358, 2962, 3325, 2062, 2799, 2537, 3298, 930, 1248, 3306, 992, 3859):
        assert by_lc_id[lc_id].section == "§2.3"
        assert by_lc_id[lc_id].is_optional is False

    # 每个 section 内部的 is_optional 不是随便混的：整节标题写了"选做"的
    # （§1.2/§2.4）必须全员选做；其余没有该标注、也没有嵌套"####"/加粗细化
    # 的 section（§1.1/§2.2/§3.1/§3.3/§3.4/§3.6/§4.1/§4.2/§6）必须全员非
    # 选做。§2.1/§2.3/§3.2/§3.5/§5 是两者都有的混合 section（分别来自嵌套的
    # "#### 进阶（选做）"/"思维扩展（选做）"/"思维扩展"），上面的精确计数
    # 已经钉住了它们的比例。
    fully_optional = {"§1.2", "§2.4"}
    fully_required = {
        "§1.1", "§2.2", "§3.1", "§3.3", "§3.4", "§3.6", "§4.1", "§4.2", "§6",
    }
    for section, c in counts.items():
        if section in fully_optional:
            assert c["optional"] == c["total"], section
        elif section in fully_required:
            assert c["optional"] == 0, section

    assert set(counts) == fully_optional | fully_required | {
        "§2.1", "§2.3", "§3.2", "§3.5", "§5",
    }


def test_shipped_sliding_window_default_template_resolution():
    """resolve_section_template 通过 topic.yaml 的 section_templates 按最长
    前缀匹配，把每题的 section 解到 templates.yaml 里的某个模板代码上（或者
    解不到、留 None）。这里直接在真实的 223 题目录上验证三种代表情况：
    §1.1 有模板（A）、§2.2 有模板（C，且不是被 "§1" 前缀污染的 A）、§4.1 没
    配模板（None，这是设计好的，不是漏配——见 topic.yaml 的注释）。
    """
    bundle = load_bundle(SHIPPED_SLIDING_WINDOW_DIR)
    by_section_first: dict[str, str | None] = {}
    for problem in bundle.problems:
        by_section_first.setdefault(problem.section, problem.default_template)

    assert by_section_first["§1.1"] == "A"
    assert by_section_first["§2.2"] == "C"
    assert by_section_first["§4.1"] is None

    # 同一件事也直接用 resolve_section_template 验证一遍，不经过 problems.yaml
    # 这层间接——两边应该完全一致。
    section_templates = bundle.config.section_templates
    assert resolve_section_template("§1.1", section_templates) == "A"
    assert resolve_section_template("§2.2", section_templates) == "C"
    assert resolve_section_template("§4.1", section_templates) is None
