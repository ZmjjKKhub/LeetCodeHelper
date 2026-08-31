"""读取并交叉校验 data/topics/<code>/ 下的四份 YAML。纯函数，不碰 DB。

校验失败即抛异常，绝不部分写库——见规格 §9.3。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from leetcode_helper.models import Difficulty
from leetcode_helper.services.topics import TopicConfig, TopicConfigError, parse_topic_config


class SeedBundleError(ValueError):
    """种子数据不合法。"""


@dataclass(frozen=True)
class SeedProblem:
    lc_id: int
    title: str
    url: str
    difficulty: Difficulty
    section: str
    section_name: str
    is_starred: bool
    is_premium: bool
    is_optional: bool
    default_template: str | None


@dataclass(frozen=True)
class SeedTemplate:
    code: str
    name: str
    language: str
    content: str
    pitfalls: str
    trigger_signal: str


@dataclass(frozen=True)
class SeedPlanDay:
    day_index: int
    phase: str
    theme: str
    problem_lc_ids: tuple[int, ...]


@dataclass(frozen=True)
class SeedPlan:
    name: str
    start_date: date
    days: tuple[SeedPlanDay, ...]


@dataclass(frozen=True)
class SeedBundle:
    config: TopicConfig
    problems: tuple[SeedProblem, ...]
    templates: tuple[SeedTemplate, ...]
    plan: SeedPlan


def _read_yaml(path: Path, expected: type):
    if not path.exists():
        raise SeedBundleError(f"缺少文件: {path.name}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(data, expected):
        raise SeedBundleError(
            f"{path.name} 的顶层必须是 {expected.__name__}，实际是 {type(data).__name__}"
        )
    return data


def _parse_templates(raw: list) -> tuple[SeedTemplate, ...]:
    templates: list[SeedTemplate] = []
    seen: set[str] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise SeedBundleError(f"templates.yaml 里有条目不是合法的映射: {entry!r}")
        code = entry.get("code")
        if not code:
            raise SeedBundleError("templates.yaml 里有条目缺少 code")
        if code in seen:
            raise SeedBundleError(f"templates.yaml 的 code 重复: {code}")
        seen.add(code)
        templates.append(
            SeedTemplate(
                code=code,
                name=entry.get("name") or code,
                language=entry.get("language") or "python",
                content=entry.get("content") or "",
                pitfalls=entry.get("pitfalls") or "",
                trigger_signal=entry.get("trigger_signal") or "",
            )
        )
    return tuple(templates)


def _parse_problems(raw: list, template_codes: set[str]) -> tuple[SeedProblem, ...]:
    if not raw:
        raise SeedBundleError("problems.yaml 不能为空，至少需要一道题目")

    problems: list[SeedProblem] = []
    seen: set[int] = set()
    for entry in raw:
        if not isinstance(entry, dict):
            raise SeedBundleError(f"problems.yaml 里有条目不是合法的映射: {entry!r}")
        lc_id = entry.get("lc_id")
        if not isinstance(lc_id, int) or isinstance(lc_id, bool):
            raise SeedBundleError(f"problems.yaml 里有条目的 lc_id 非法: {lc_id!r}")
        if lc_id in seen:
            raise SeedBundleError(f"problems.yaml 的 lc_id 重复: {lc_id}")
        seen.add(lc_id)

        if not entry.get("section"):
            raise SeedBundleError(f"lc_id={lc_id} 的 section 不能为空")

        raw_difficulty = entry.get("difficulty")
        try:
            difficulty = Difficulty(raw_difficulty)
        except ValueError:
            raise SeedBundleError(
                f"lc_id={lc_id} 的 difficulty 非法: {raw_difficulty}，只接受 easy/medium/hard"
            ) from None

        default_template = entry.get("default_template")
        if default_template is not None and default_template not in template_codes:
            raise SeedBundleError(
                f"lc_id={lc_id} 的 default_template={default_template} 不存在于 templates.yaml"
            )

        problems.append(
            SeedProblem(
                lc_id=lc_id,
                title=entry.get("title") or "",
                url=entry.get("url") or "",
                difficulty=difficulty,
                section=entry["section"],
                section_name=entry.get("section_name") or "",
                is_starred=bool(entry.get("is_starred")),
                is_premium=bool(entry.get("is_premium")),
                is_optional=bool(entry.get("is_optional")),
                default_template=default_template,
            )
        )
    return tuple(problems)


def _parse_plan(raw: dict, known_lc_ids: set[int]) -> SeedPlan:
    start_date = raw.get("start_date")
    if isinstance(start_date, datetime) or not isinstance(start_date, date):
        raise SeedBundleError(f"plan_default.yaml 的 start_date 非法: {start_date!r}")

    days_raw = raw.get("days")
    if not isinstance(days_raw, list) or not days_raw:
        raise SeedBundleError("plan_default.yaml 的 days 不能为空，至少需要一天")

    days: list[SeedPlanDay] = []
    seen: set[int] = set()
    for entry in days_raw:
        if not isinstance(entry, dict):
            raise SeedBundleError(f"plan_default.yaml 的 days 里有条目不是合法的映射: {entry!r}")
        day_index = entry.get("day_index")
        if not isinstance(day_index, int) or isinstance(day_index, bool):
            raise SeedBundleError(f"plan_default.yaml 的 day_index 非法: {day_index!r}")
        if day_index in seen:
            raise SeedBundleError(f"plan_default.yaml 的 day_index 重复: {day_index}")
        seen.add(day_index)

        problems_raw = entry.get("problems") if entry.get("problems") is not None else []
        if not isinstance(problems_raw, list):
            raise SeedBundleError(
                f"plan_default.yaml 第 {day_index} 天的 problems 必须是列表，"
                f"实际是 {type(problems_raw).__name__}"
            )
        lc_ids = tuple(problems_raw)
        for lc_id in lc_ids:
            if lc_id not in known_lc_ids:
                raise SeedBundleError(
                    f"plan_default.yaml 第 {day_index} 天引用了不存在的 lc_id: {lc_id}"
                )

        days.append(
            SeedPlanDay(
                day_index=day_index,
                phase=entry.get("phase") or "",
                theme=entry.get("theme") or "",
                problem_lc_ids=lc_ids,
            )
        )

    return SeedPlan(
        name=raw.get("name") or "默认计划",
        start_date=start_date,
        days=tuple(sorted(days, key=lambda d: d.day_index)),
    )


def load_bundle(topic_dir: Path) -> SeedBundle:
    try:
        config = parse_topic_config(_read_yaml(topic_dir / "topic.yaml", dict))
    except TopicConfigError as exc:
        raise SeedBundleError(str(exc)) from exc

    templates = _parse_templates(_read_yaml(topic_dir / "templates.yaml", list))
    problems = _parse_problems(
        _read_yaml(topic_dir / "problems.yaml", list), {t.code for t in templates}
    )
    plan = _parse_plan(
        _read_yaml(topic_dir / "plan_default.yaml", dict), {p.lc_id for p in problems}
    )
    return SeedBundle(config=config, problems=problems, templates=templates, plan=plan)
