import pytest

from leetcode_helper.models import Difficulty
from leetcode_helper.services.topics import (
    TopicConfigError,
    parse_topic_config,
    parse_topic_config_json,
    resolve_section_template,
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


def test_raw_must_be_dict():
    with pytest.raises(TopicConfigError, match="顶层必须是 dict"):
        parse_topic_config(["not", "a", "dict"])


def test_code_must_be_string():
    raw = {**VALID, "code": 123}
    with pytest.raises(TopicConfigError, match="code 不能为空，且必须是字符串"):
        parse_topic_config(raw)


def test_time_limits_wrong_type_rejected():
    raw = {**VALID, "time_limits": "nope"}
    with pytest.raises(TopicConfigError, match="time_limits 必须是 dict，实际是 str"):
        parse_topic_config(raw)


def test_options_must_be_string_list():
    raw = {
        **VALID,
        "card_fields": [{"key": "a", "label": "A", "type": "choice", "options": "abc"}],
    }
    with pytest.raises(TopicConfigError, match="options 必须是字符串列表"):
        parse_topic_config(raw)


def test_card_fields_wrong_type_rejected():
    raw = {**VALID, "card_fields": "nope"}
    with pytest.raises(TopicConfigError, match="card_fields 必须是 list，实际是 str"):
        parse_topic_config(raw)


def test_section_templates_defaults_to_empty_dict():
    config = parse_topic_config(VALID)
    assert config.section_templates == {}


def test_section_templates_parsed():
    raw = {**VALID, "section_templates": {"§1": "A", "§2.2": "C"}}
    config = parse_topic_config(raw)
    assert config.section_templates == {"§1": "A", "§2.2": "C"}


def test_section_templates_wrong_type_rejected():
    raw = {**VALID, "section_templates": ["§1", "A"]}
    with pytest.raises(TopicConfigError, match="section_templates 必须是 dict，实际是 list"):
        parse_topic_config(raw)


def test_section_templates_empty_key_rejected():
    raw = {**VALID, "section_templates": {"": "A"}}
    with pytest.raises(TopicConfigError, match="section_templates 的 key 不能为空"):
        parse_topic_config(raw)


def test_section_templates_non_string_value_rejected():
    raw = {**VALID, "section_templates": {"§1": 1}}
    with pytest.raises(TopicConfigError, match=r"section_templates\.§1 的值必须是非空字符串"):
        parse_topic_config(raw)


def test_section_templates_roundtrips_through_json():
    raw = {**VALID, "section_templates": {"§1": "A"}}
    config = parse_topic_config(raw)
    assert parse_topic_config_json(config.to_json()) == config


# --- resolve_section_template: longest matching section prefix ---


def test_resolve_section_template_longest_prefix_wins():
    mapping = {"§1": "A", "§2.1": "B", "§2.2": "C", "§2.3": "D"}
    # §1.1 and §1.2 both fall back to the general "§1" key.
    assert resolve_section_template("§1.1", mapping) == "A"
    assert resolve_section_template("§1.2", mapping) == "A"


def test_resolve_section_template_prefers_specific_over_general_key():
    # Both "§2" and "§2.2" are present and both match "§2.2" as a prefix --
    # the more specific "§2.2" key must win, not the shorter "§2".
    mapping = {"§2": "X", "§2.2": "C"}
    assert resolve_section_template("§2.2", mapping) == "C"


def test_resolve_section_template_unmatched_section_returns_none():
    mapping = {"§1": "A", "§2.1": "B"}
    assert resolve_section_template("§3.1", mapping) is None


def test_resolve_section_template_empty_mapping_returns_none():
    assert resolve_section_template("§1.1", {}) is None
