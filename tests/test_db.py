from pathlib import Path

from leetcode_helper.db import resolve_db_path


def test_resolve_db_path_default(tmp_path, monkeypatch):
    monkeypatch.delenv("LCH_DB_PATH", raising=False)
    assert resolve_db_path(project_root=tmp_path) == tmp_path / "data" / "app.db"


def test_resolve_db_path_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("LCH_DB_PATH", str(tmp_path / "custom.db"))
    assert resolve_db_path(project_root=Path("/ignored")) == tmp_path / "custom.db"
