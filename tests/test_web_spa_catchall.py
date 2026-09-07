"""app_factory.create_app() mounts the React SPA's build output
(frontend/dist) at the root, behind a catch-all route (see
leetcode_helper/web/app_factory.py, FRONTEND_DIST_DIR). That catch-all must
never shadow /api/* or /assets/*, must still serve the SPA shell on a hard
reload of any client-side route (/, /history, and anything else React
Router owns), and /today (the old Jinja page's URL) must redirect instead of
falling through to it. This is the regression guard for all of that,
covering both the "frontend/dist exists" and "not built yet" branches.
"""

from __future__ import annotations

from pathlib import Path

import leetcode_helper.web.app_factory as app_factory_module

from .conftest import make_client, seed

REAL_DIST_INDEX = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "index.html"


def test_api_still_works_regardless_of_frontend_dist(engine):
    seed(engine, with_plan=False)
    client = make_client(engine)

    meta = client.get("/api/meta")
    assert meta.status_code == 200
    assert meta.headers["content-type"].startswith("application/json")
    assert meta.json()["topic"]["code"] == "sliding-window"


def test_today_redirects_to_root(engine):
    # /today was the old Jinja page's URL -- it must not fall through to the
    # SPA catch-all (which would serve index.html at a URL the React app
    # itself never routes to); it redirects to "/" instead.
    seed(engine, with_plan=False)
    client = make_client(engine)

    response = client.get("/today", follow_redirects=False)
    assert response.status_code == 307
    assert response.headers["location"] == "/"


def test_missing_frontend_dist_serves_actionable_notice_not_a_crash(engine, monkeypatch, tmp_path):
    seed(engine, with_plan=False)
    monkeypatch.setattr(app_factory_module, "FRONTEND_DIST_DIR", tmp_path / "does-not-exist")

    client = make_client(engine)
    response = client.get("/")

    assert response.status_code == 503
    assert "npm run build" in response.text


def test_missing_frontend_dist_does_not_break_api(engine, monkeypatch, tmp_path):
    seed(engine, with_plan=False)
    monkeypatch.setattr(app_factory_module, "FRONTEND_DIST_DIR", tmp_path / "does-not-exist")

    client = make_client(engine)
    assert client.get("/api/meta").status_code == 200


def test_root_serves_the_built_spa_index_when_dist_present(engine):
    if not REAL_DIST_INDEX.is_file():
        import pytest

        pytest.skip("frontend/dist not built -- run `cd frontend && npm run build` first")

    seed(engine, with_plan=False)
    client = make_client(engine)

    response = client.get("/")
    assert response.status_code == 200
    assert 'id="root"' in response.text


def test_history_hard_reload_serves_the_spa_shell_not_a_404(engine):
    if not REAL_DIST_INDEX.is_file():
        import pytest

        pytest.skip("frontend/dist not built -- run `cd frontend && npm run build` first")

    seed(engine, with_plan=False)
    client = make_client(engine)

    # A hard load of /history (deep link, not client-side navigation) must
    # still resolve -- the catch-all serves the same index.html React
    # Router then renders the History page from, not a 404.
    response = client.get("/history")
    assert response.status_code == 200
    assert 'id="root"' in response.text


def test_unknown_path_serves_the_spa_shell_when_dist_present(engine):
    if not REAL_DIST_INDEX.is_file():
        import pytest

        pytest.skip("frontend/dist not built -- run `cd frontend && npm run build` first")

    seed(engine, with_plan=False)
    client = make_client(engine)

    response = client.get("/some/unknown/route")
    assert response.status_code == 200
    assert 'id="root"' in response.text
