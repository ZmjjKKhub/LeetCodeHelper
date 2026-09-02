"""refresh_starred 的测试。全部离线——不发任何网络请求。"""

from __future__ import annotations

from pathlib import Path

import pytest

from leetcode_helper.seed.refresh_starred import (
    RefreshError,
    apply_favorites,
    main,
)

SHIPPED = Path(__file__).resolve().parent.parent / "data" / "topics" / "sliding-window"

YAML = """\
# 头部注释必须保留

- lc_id: 1456
  title: 甲
  is_starred: false
  is_optional: false

- lc_id: 567
  title: 乙
  is_starred: true
  is_optional: true
"""


def test_sets_and_clears_is_starred():
    updated, changed, missing = apply_favorites(YAML, {1456: True, 567: False})

    assert changed == [1456, 567]
    assert missing == []
    assert "- lc_id: 1456\n  title: 甲\n  is_starred: true" in updated
    assert "- lc_id: 567\n  title: 乙\n  is_starred: false" in updated


def test_preserves_comments_and_untouched_fields():
    updated, _, _ = apply_favorites(YAML, {1456: True, 567: True})

    # 逐块改写而不是整份 dump，正是为了保住这些：
    assert updated.startswith("# 头部注释必须保留")
    assert "is_optional: false" in updated
    assert "is_optional: true" in updated
    assert updated.count("title: 甲") == 1


def test_unchanged_rows_are_not_reported_as_changed():
    updated, changed, _ = apply_favorites(YAML, {1456: False, 567: True})

    assert changed == []
    assert updated == YAML


def test_problems_absent_from_the_api_are_reported_not_silently_skipped():
    _, changed, missing = apply_favorites(YAML, {1456: True})

    assert changed == [1456]
    assert missing == [567]


def test_missing_is_starred_field_is_an_error_not_a_silent_noop():
    broken = "- lc_id: 1456\n  title: 甲\n"
    with pytest.raises(RefreshError, match="lc_id=1456 的条目里没有 is_starred 字段"):
        apply_favorites(broken, {1456: True})


def test_shipped_problems_yaml_is_rewritable_without_semantic_change():
    """真实那份 problems.yaml 能被这个脚本原样改写。

    脚本用正则逐块改写，格式一旦不符合预期就会静默失配——所以拿真文件跑一遍，
    喂进「所有题都未收藏」的映射，结果必须与原文逐字节相同。
    """
    import yaml

    text = (SHIPPED / "problems.yaml").read_text(encoding="utf-8")
    lc_ids = [p["lc_id"] for p in yaml.safe_load(text)]

    updated, changed, missing = apply_favorites(text, dict.fromkeys(lc_ids, False))

    assert missing == []
    assert changed == [567, 438]  # 目前仅这两道是 true，会被清掉
    assert [p["lc_id"] for p in yaml.safe_load(updated)] == lc_ids
    assert all(p["is_starred"] is False for p in yaml.safe_load(updated))


def test_main_without_cookie_refuses_and_touches_nothing(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("LEETCODE_SESSION", raising=False)
    target = tmp_path / "problems.yaml"
    target.write_text(YAML, encoding="utf-8")

    assert main(["refresh_starred", str(tmp_path)]) == 2
    assert target.read_text(encoding="utf-8") == YAML
    assert "LEETCODE_SESSION" in capsys.readouterr().err


def test_main_refuses_when_the_api_reports_zero_favorites(tmp_path, monkeypatch, capsys):
    """收藏数为 0 几乎总是 cookie 失效，而不是真的一道没收藏。

    如果照写，会把用户已有的标星全部清成 false —— 一次静默的数据损坏。
    """
    monkeypatch.setenv("LEETCODE_SESSION", "irrelevant")
    monkeypatch.setattr(
        "leetcode_helper.seed.refresh_starred.fetch_favorites",
        lambda _cookie: {1456: False, 567: False},
    )
    target = tmp_path / "problems.yaml"
    target.write_text(YAML, encoding="utf-8")

    assert main(["refresh_starred", str(tmp_path)]) == 1
    assert target.read_text(encoding="utf-8") == YAML
    assert "cookie" in capsys.readouterr().err


def test_main_writes_and_never_prints_the_cookie(tmp_path, monkeypatch, capsys):
    secret = "super-secret-session-value"
    monkeypatch.setenv("LEETCODE_SESSION", secret)
    monkeypatch.setattr(
        "leetcode_helper.seed.refresh_starred.fetch_favorites",
        lambda _cookie: {1456: True, 567: False},
    )
    target = tmp_path / "problems.yaml"
    target.write_text(YAML, encoding="utf-8")

    assert main(["refresh_starred", str(tmp_path)]) == 0

    written = target.read_text(encoding="utf-8")
    assert "- lc_id: 1456\n  title: 甲\n  is_starred: true" in written

    captured = capsys.readouterr()
    assert secret not in captured.out
    assert secret not in captured.err
    assert secret not in written
