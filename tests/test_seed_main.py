from pathlib import Path

import pytest
from sqlmodel import Session, SQLModel, select

import leetcode_helper.db as db
from leetcode_helper.models import Problem, Topic
from leetcode_helper.seed.__main__ import main

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


def _write_topic_dir(tmp_path, *, topic=TOPIC_YAML, templates=TEMPLATES_YAML,
                      problems=PROBLEMS_YAML, plan=PLAN_YAML):
    topic_dir = tmp_path / "topic_dir"
    topic_dir.mkdir()
    (topic_dir / "topic.yaml").write_text(topic, encoding="utf-8")
    (topic_dir / "templates.yaml").write_text(templates, encoding="utf-8")
    (topic_dir / "problems.yaml").write_text(problems, encoding="utf-8")
    (topic_dir / "plan_default.yaml").write_text(plan, encoding="utf-8")
    return topic_dir


@pytest.fixture
def temp_db(tmp_path, monkeypatch):
    """Point LCH_DB_PATH at a fresh temp sqlite file, with tables already
    created (as `alembic upgrade head` would do before a real seed run), and
    reset db's module-level engine cache so it picks up the new path."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("LCH_DB_PATH", str(db_path))
    monkeypatch.setattr(db, "_engine", None)
    engine = db.make_engine(db_path)
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(db, "_engine", engine)
    yield db_path


def test_main_wrong_argc_returns_2(capsys):
    assert main(["prog"]) == 2
    assert main(["prog", "a", "b"]) == 2
    captured = capsys.readouterr()
    assert "用法" in captured.err


def test_main_invalid_bundle_returns_1_and_writes_nothing(tmp_path, temp_db, capsys):
    # missing templates.yaml etc. -> load_bundle raises SeedBundleError
    empty_dir = tmp_path / "empty_topic"
    empty_dir.mkdir()

    exit_code = main(["prog", str(empty_dir)])

    assert exit_code == 1
    captured = capsys.readouterr()
    assert "校验失败" in captured.err

    with Session(db.get_engine()) as session:
        assert session.exec(select(Topic)).all() == []
        assert session.exec(select(Problem)).all() == []


def test_main_success_returns_0_and_writes_db(tmp_path, temp_db, capsys):
    topic_dir = _write_topic_dir(tmp_path)

    exit_code = main(["prog", str(topic_dir)])

    assert exit_code == 0
    captured = capsys.readouterr()
    assert "导入完成" in captured.out

    with Session(db.get_engine()) as session:
        topic = session.exec(select(Topic)).one()
        assert topic.code == "sliding-window"
        assert len(session.exec(select(Problem)).all()) == 1


def test_main_rerun_is_idempotent(tmp_path, temp_db, capsys):
    topic_dir = _write_topic_dir(tmp_path)

    assert main(["prog", str(topic_dir)]) == 0
    capsys.readouterr()
    assert main(["prog", str(topic_dir)]) == 0

    with Session(db.get_engine()) as session:
        assert len(session.exec(select(Topic)).all()) == 1
        assert len(session.exec(select(Problem)).all()) == 1
