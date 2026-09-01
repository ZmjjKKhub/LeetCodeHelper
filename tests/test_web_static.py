"""The app must work fully offline (spec constraint C3): Pico/HTMX/Alpine are
vendored under web/static/vendor and served locally, never fetched from a CDN.
"""

from __future__ import annotations

from pathlib import Path

from tests.conftest import make_client, seed

TEMPLATES_DIR = Path(__file__).resolve().parent.parent / "leetcode_helper" / "web" / "templates"

VENDOR_ASSETS = [
    "/static/vendor/pico.min.css",
    "/static/vendor/htmx.min.js",
    "/static/vendor/alpine.min.js",
]


def test_vendored_assets_are_served(engine):
    seed(engine, with_plan=False)
    client = make_client(engine)
    for path in VENDOR_ASSETS:
        response = client.get(path)
        assert response.status_code == 200, path
        assert len(response.content) > 0, path


def test_no_template_references_a_cdn():
    offenders = []
    for path in TEMPLATES_DIR.rglob("*.html"):
        text = path.read_text(encoding="utf-8")
        if "cdn.jsdelivr.net" in text:
            offenders.append(str(path))
    assert offenders == []
