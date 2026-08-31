import pytest

from leetcode_helper.models import Difficulty
from leetcode_helper.services.topics import (
    TopicConfigError,
    parse_topic_config,
    parse_topic_config_json,
    time_limit_for,
)

VALID = {
    "code": "sliding-window",
    "name": "滑动窗口",
    "time_limits": {"easy": 480, "medium": 1200, "hard": 2100},
    "card_fields": [
        {"key": "trigger_feature", "label": "触发特征", "type": "text"},
        {
            "key": "count_timing",
            "label": "统计时机",
            "type": "choice",
            "options": ["入窗后", "出窗循环内", "出窗循环外"],
        },
    ],
}


def test_parse_valid_config():
    config = parse_topic_config(VALID)
    assert config.code == "sliding-window"
    assert config.time_limits["medium"] == 1200
    assert len(config.card_fields) == 2
    assert config.card_fields[1].options == ("入窗后", "出窗循环内", "出窗循环外")


def test_time_limit_for_difficulty():
    config = parse_topic_config(VALID)
    assert time_limit_for(config, Difficulty.easy) == 480
    assert time_limit_for(config, Difficulty.hard) == 2100


def test_missing_time_limit_key_rejected():
    raw = {**VALID, "time_limits": {"easy": 480, "medium": 1200}}
    with pytest.raises(TopicConfigError, match="time_limits 缺少 hard"):
        parse_topic_config(raw)


def test_non_positive_time_limit_rejected():
    raw = {**VALID, "time_limits": {"easy": 0, "medium": 1200, "hard": 2100}}
    with pytest.raises(TopicConfigError, match="time_limits.easy 必须是正整数"):
        parse_topic_config(raw)


def test_duplicate_card_field_key_rejected():
    raw = {
        **VALID,
        "card_fields": [
            {"key": "a", "label": "A", "type": "text"},
            {"key": "a", "label": "A2", "type": "text"},
        ],
    }
    with pytest.raises(TopicConfigError, match="card_fields 的 key 重复: a"):
        parse_topic_config(raw)


def test_unknown_card_field_type_rejected():
    raw = {**VALID, "card_fields": [{"key": "a", "label": "A", "type": "number"}]}
    with pytest.raises(TopicConfigError, match="card_fields.a 的 type 非法: number"):
        parse_topic_config(raw)


def test_choice_without_options_rejected():
    raw = {**VALID, "card_fields": [{"key": "a", "label": "A", "type": "choice"}]}
    with pytest.raises(TopicConfigError, match="card_fields.a 是 choice，必须有非空 options"):
        parse_topic_config(raw)


def test_config_roundtrips_through_json():
    config = parse_topic_config(VALID)
    assert parse_topic_config_json(config.to_json()) == config
