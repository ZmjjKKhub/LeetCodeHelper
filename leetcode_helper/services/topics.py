"""topic.yaml 的解析与校验。纯函数，不碰 DB。"""

from __future__ import annotations

import json
from dataclasses import dataclass

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

    return TopicConfig(
        code=raw["code"],
        name=raw["name"],
        time_limits=time_limits,
        card_fields=tuple(fields),
    )


def parse_topic_config_json(text: str) -> TopicConfig:
    return parse_topic_config(json.loads(text))


def time_limit_for(config: TopicConfig, difficulty: Difficulty) -> int:
    return config.time_limits[difficulty.value]
