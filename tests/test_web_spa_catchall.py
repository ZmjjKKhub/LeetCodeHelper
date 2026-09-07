"""app_factory.create_app() mounts the React SPA's build output
(frontend/dist) behind a catch-all route (see leetcode_helper/web/
app_factory.py, FRONTEND_DIST_DIR). That catch-all must never shadow the
existing Jinja pages or JSON API -- this is the regression guard for that,
covering both the "frontend/dist exists" and "not built yet" branches.
"""

from __future__ import annotations

from pathlib import Path

import leetcode_helper.web.app_factory as app_factory_module

from .conftest import make_client, seed

REAL_DIST_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"


def test_today_history_and_api_still_work_regardless_of_frontend_dist(engine):
    seed(engine, with_plan=False)
    client = make_client(engine)

    today = client.get("/today")
    assert today.status_code == 200
    assert "长度最小的子数组" in today.text

    history = client.get("/history")
    assert history.status_code == 200

    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.headers["content-type"].startswith("application/json")
    assert meta.json()["topic"]["code"] == "sliding-window"


def test_root_still_redirects_to_today_not_the_spa(engine):
    seed(engine, with_plan=False)
    client = make_client(engine)

    response = client.get("/", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/today"


def test_unknown_path_never_returns_the_jinja_today_page(engine):
    # Whatever the catch-all returns for an unrecognized path (built SPA
    # index.html, or the "not built yet" notice), it must not somehow
    # alias onto /today's own response -- a much stranger bug than a 404,
    # but cheap to rule out explicitly.
    seed(engine, with_plan=False)
    client = make_client(engine)

    response = client.get("/some/spa/route/not/a/real/api/path")
    assert response.status_code in (200, 503)
    assert "长度最小的子数组" not in response.text


def test_missing_frontend_dist_serves_actionable_notice_not_a_crash(engine, monkeypatch, tmp_path):
    seed(engine, with_plan=False)
    monkeypatch.setattr(app_factory_module, "FRONTEND_DIST_DIR", tmp_path / "does-not-exist")

    client = make_client(engine)
    response = client.get("/some/spa/route")

    assert response.status_code == 503
    assert "npm run build" in response.text
    # The notice must not lie about the Jinja pages being broken too.
    assert "/today" in response.text or "today" in response.text.lower()


def test_missing_frontend_dist_does_not_break_today_or_api(engine, monkeypatch, tmp_path):
    seed(engine, with_plan=False)
    monkeypatch.setattr(app_factory_module, "FRONTEND_DIST_DIR", tmp_path / "does-not-exist")

    client = make_client(engine)
    assert client.get("/today").status_code == 200
    assert client.get("/api/meta").status_code == 200


def test_unknown_path_serves_the_built_spa_index_when_dist_present(engine):
    if not REAL_DIST_INDEX.is_file():
        import pytest

        pytest.skip("frontend/dist not built -- run `cd frontend && npm run build` first")

    seed(engine, with_plan=False)
    client = make_client(engine)

    response = client.get("/app")
    assert response.status_code == 200
    assert 'id="root"' in response.text
