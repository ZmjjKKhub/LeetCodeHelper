"""topic.yaml 的解析与校验。纯函数，不碰 DB。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

from leetcode_helper.models import Difficulty

FIELD_TYPES = {"text", "choice"}


class TopicConfigError(ValueError):
    """topic.yaml 不合法。"""


@dataclass(frozen=True)
class CardField:
    key: str
    label: str
    type: str
    options: tuple[str, ...] = ()


@dataclass(frozen=True)
class TopicConfig:
    code: str
    name: str
    time_limits: dict[str, int]
    card_fields: tuple[CardField, ...]
    # Optional: maps a 题单 section prefix (e.g. "§1", "§2.2") to the template
    # code every problem under that section uses. Resolved at seed-import
    # time by resolve_section_template() below, via longest matching prefix,
    # into Problem.default_template -- see seed/bundle.py::_parse_problems.
    # A topic that omits it behaves exactly as before (every problem's
    # default_template comes from its own optional per-problem override).
    section_templates: dict[str, str] = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps(
            {
                "code": self.code,
                "name": self.name,
                "time_limits": self.time_limits,
                "card_fields": [
                    {
                        "key": f.key,
                        "label": f.label,
                        "type": f.type,
                        "options": list(f.options),
                    }
                    for f in self.card_fields
                ],
                "section_templates": self.section_templates,
            },
            ensure_ascii=False,
        )


def parse_topic_config(raw: dict) -> TopicConfig:
    if not isinstance(raw, dict):
        raise TopicConfigError(f"topic 配置的顶层必须是 dict，实际是 {type(raw).__name__}")

    for key in ("code", "name"):
        value = raw.get(key)
        if not isinstance(value, str) or not value:
            raise TopicConfigError(f"{key} 不能为空，且必须是字符串")

    time_limits_raw = raw.get("time_limits")
    if time_limits_raw is None:
        time_limits_raw = {}
    if not isinstance(time_limits_raw, dict):
        raise TopicConfigError(
            f"time_limits 必须是 dict，实际是 {type(time_limits_raw).__name__}"
        )
    time_limits: dict[str, int] = {}
    for difficulty in Difficulty:
        name = difficulty.value
        if name not in time_limits_raw:
            raise TopicConfigError(f"time_limits 缺少 {name}")
        value = time_limits_raw[name]
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise TopicConfigError(f"time_limits.{name} 必须是正整数，实际是 {value!r}")
        time_limits[name] = value

    card_fields_raw = raw.get("card_fields")
    if card_fields_raw is None:
        card_fields_raw = []
    if not isinstance(card_fields_raw, list):
        raise TopicConfigError(
            f"card_fields 必须是 list，实际是 {type(card_fields_raw).__name__}"
        )

    fields: list[CardField] = []
    seen: set[str] = set()
    for entry in card_fields_raw:
        key = entry.get("key")
        if not key:
            raise TopicConfigError("card_fields 里有条目缺少 key")
        if key in seen:
            raise TopicConfigError(f"card_fields 的 key 重复: {key}")
        seen.add(key)

        field_type = entry.get("type")
        if field_type not in FIELD_TYPES:
            raise TopicConfigError(f"card_fields.{key} 的 type 非法: {field_type}")

        options_raw = entry.get("options")
        if options_raw is None:
            options_raw = []
        if not isinstance(options_raw, list) or not all(
            isinstance(option, str) for option in options_raw
        ):
            raise TopicConfigError(f"card_fields.{key} 的 options 必须是字符串列表")
        options = tuple(options_raw)
        if field_type == "choice" and not options:
            raise TopicConfigError(f"card_fields.{key} 是 choice，必须有非空 options")

        fields.append(
            CardField(key=key, label=entry.get("label") or key, type=field_type, options=options)
        )

    section_templates_raw = raw.get("section_templates")
    if section_templates_raw is None:
        section_templates_raw = {}
    if not isinstance(section_templates_raw, dict):
        raise TopicConfigError(
            f"section_templates 必须是 dict，实际是 {type(section_templates_raw).__name__}"
        )
    section_templates: dict[str, str] = {}
    for section_key, template_code in section_templates_raw.items():
        if not isinstance(section_key, str) or not section_key:
            raise TopicConfigError("section_templates 的 key 不能为空，且必须是字符串")
        if not isinstance(template_code, str) or not template_code:
            raise TopicConfigError(
                f"section_templates.{section_key} 的值必须是非空字符串，实际是 {template_code!r}"
            )
        section_templates[section_key] = template_code

    return TopicConfig(
        code=raw["code"],
        name=raw["name"],
        time_limits=time_limits,
        card_fields=tuple(fields),
        section_templates=section_templates,
    )


def parse_topic_config_json(text: str) -> TopicConfig:
    return parse_topic_config(json.loads(text))


def time_limit_for(config: TopicConfig, difficulty: Difficulty) -> int:
    return config.time_limits[difficulty.value]


def resolve_section_template(section: str, section_templates: dict[str, str]) -> str | None:
    """Longest-prefix match: `section` (e.g. "§1.1") resolves to the template
    code of whichever key in `section_templates` is both a prefix of it and
    the longest such prefix -- so a specific "§2.2" key wins over a more
    general "§2" key that also matches, while "§1.1"/"§1.2" both fall back to
    a bare "§1" key. Returns None when no key is a prefix of `section`.

    Pure and DB-free on purpose: this is a rule about topic configuration
    shape, the same reason parse_topic_config lives here rather than in
    seed/bundle.py.
    """
    best_key: str | None = None
    for key in section_templates:
        if section.startswith(key) and (best_key is None or len(key) > len(best_key)):
            best_key = key
    return section_templates[best_key] if best_key is not None else None
