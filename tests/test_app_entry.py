"""Tests for app.py, the process entry point.

None of these start a real server or open a real browser -- uvicorn.run
and webbrowser.open are always monkeypatched or simply never reached.
"""

from __future__ import annotations

import pytest
from sqlalchemy import create_engine
from sqlmodel import SQLModel


def test_importing_app_module_does_not_touch_real_db():
    # The plan's original app.py called create_app() (-> get_engine() ->
    # a real sqlite connection to data/app.db) at import time. Guard against
    # that regression: merely importing this module must leave
    # leetcode_helper.db's lazily-initialized global engine untouched.
    import leetcode_helper.db as db_module

    assert db_module._engine is None
    import app  # noqa: F401

    assert db_module._engine is None


def test_build_app_returns_configured_asgi_app():
    import app as app_module

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    built = app_module.build_app(engine=engine)

    assert built.title == "刷题复盘系统"


def test_ensure_schema_ready_false_when_no_tables():
    import app as app_module

    empty_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    assert app_module._ensure_schema_ready(empty_engine) is False


def test_ensure_schema_ready_true_once_migrated():
    import app as app_module

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    assert app_module._ensure_schema_ready(engine) is True


def test_main_refuses_to_start_when_schema_missing(monkeypatch, capsys):
    import app as app_module

    empty_engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    monkeypatch.setattr(app_module, "get_engine", lambda: empty_engine)

    def _fail_if_called(*_args, **_kwargs):
        pytest.fail("uvicorn.run must not be called when the schema isn't ready")

    monkeypatch.setattr(app_module.uvicorn, "run", _fail_if_called)

    with pytest.raises(SystemExit) as exc_info:
        app_module.main()

    assert exc_info.value.code != 0
    err = capsys.readouterr().err
    assert "alembic upgrade head" in err
    assert "leetcode_helper.seed" in err


def test_main_starts_server_when_schema_ready(monkeypatch):
    import app as app_module

    engine = create_engine("sqlite://", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    monkeypatch.setattr(app_module, "get_engine", lambda: engine)

    calls = []
    monkeypatch.setattr(app_module.uvicorn, "run", lambda *a, **k: calls.append((a, k)))
    monkeypatch.setattr(
        app_module.threading, "Thread", lambda *a, **k: type("T", (), {"start": lambda self: None})()
    )

    app_module.main()

    assert len(calls) == 1
    (app_arg,), kwargs = calls[0]
    assert app_arg.title == "刷题复盘系统"
    assert kwargs["host"] == app_module.HOST
    assert kwargs["port"] == app_module.PORT


def test_open_browser_when_ready_opens_once_port_is_listening(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "_port_is_open", lambda host, port, timeout=0.2: True)
    calls = []
    monkeypatch.setattr(app_module.webbrowser, "open", lambda url: calls.append(url))

    app_module._open_browser_when_ready(
        app_module.HOST, app_module.PORT, "http://x/today", attempts=3, interval=0
    )

    assert calls == ["http://x/today"]


def test_open_browser_when_ready_gives_up_if_port_never_opens(monkeypatch):
    import app as app_module

    monkeypatch.setattr(app_module, "_port_is_open", lambda host, port, timeout=0.2: False)
    calls = []
    monkeypatch.setattr(app_module.webbrowser, "open", lambda url: calls.append(url))

    app_module._open_browser_when_ready(
        app_module.HOST, app_module.PORT, "http://x/today", attempts=3, interval=0
    )

    assert calls == []
