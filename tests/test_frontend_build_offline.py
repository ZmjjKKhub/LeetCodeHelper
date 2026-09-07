"""Regression guard for spec constraint C3 (offline-capable): the React
SPA's built output (frontend/dist) must never reference an external
domain -- no CDN fonts, no CDN scripts, nothing fetched over the network
at runtime. The v1 Jinja/HTMX/Alpine stack (since removed) lost offline
support exactly this way, via a stray CDN reference nobody caught.

frontend/dist is gitignored (it's a build artifact, per spec C5), so this
test skips with a clear reason if it hasn't been built yet -- it is not a
substitute for actually running `npm run build` and inspecting the output,
which the task's own verification step does separately.
"""

from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import urlparse

import pytest

DIST_DIR = Path(__file__).resolve().parent.parent / "frontend" / "dist"

URL_RE = re.compile(r"https?://[^\s\"'()<>\\`;{}]+")

# Hosts that legitimately appear in the built output without the running
# page ever fetching them -- verified by hand against the actual dist/
# output while writing this test, not guessed:
#   - www.w3.org      SVG/MathML XML namespace URI constant (createElementNS),
#                      not a request.
#   - localhost       react-router's internal placeholder base URL, used only
#                      as the second argument to `new URL(path, base)` to
#                      resolve relative paths -- never dereferenced.
#   - react.dev        React's production build replaces full warning text
#                      with a short code + a "look this up" link
#                      (https://react.dev/errors/<code>); the link is text
#                      inside a thrown Error, read by a human, never
#                      requested by the page itself.
#   - reactrouter.com  Same pattern: react-router's invariant() error
#                      messages embed a docs link as text, not a fetch.
#   - tailwindcss.com  Tailwind stamps a one-line license/credit comment
#                      into its generated CSS; a comment, not a resource load.
# A real regression (a CDN <link>/<script src>, an @import of Google
# Fonts, a fetch() to a third-party API baked into the bundle) would
# introduce a *new* host not on this list, and must fail the test.
ALLOWED_HOSTS = {
    "www.w3.org",
    "localhost",
    "react.dev",
    "reactrouter.com",
    "tailwindcss.com",
}

CHECKED_SUFFIXES = {".html", ".css", ".js"}


def _offenders_in(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8", errors="replace")
    offenders = []
    for url in URL_RE.findall(text):
        host = urlparse(url).hostname
        if host not in ALLOWED_HOSTS:
            offenders.append(url)
    return offenders


def test_dist_output_references_no_external_domain():
    if not DIST_DIR.is_dir():
        pytest.skip(f"{DIST_DIR} does not exist -- run `cd frontend && npm run build` first")

    offenders: dict[str, list[str]] = {}
    for path in DIST_DIR.rglob("*"):
        if path.is_file() and path.suffix in CHECKED_SUFFIXES:
            found = _offenders_in(path)
            if found:
                offenders[str(path.relative_to(DIST_DIR))] = found

    assert offenders == {}, (
        "frontend/dist references external domain(s) not on the reviewed "
        f"allowlist -- this breaks offline use (spec C3): {offenders}"
    )


def test_dist_output_exists_and_is_non_empty():
    # Sanity check paired with the skip above: if frontend/dist exists but
    # is somehow empty (a half-finished build), the "no offenders found"
    # result of the test above would be vacuously true. Guard against that.
    if not DIST_DIR.is_dir():
        pytest.skip(f"{DIST_DIR} does not exist -- run `cd frontend && npm run build` first")

    files = [p for p in DIST_DIR.rglob("*") if p.is_file()]
    assert files, f"{DIST_DIR} exists but contains no files"
    assert (DIST_DIR / "index.html").is_file()
