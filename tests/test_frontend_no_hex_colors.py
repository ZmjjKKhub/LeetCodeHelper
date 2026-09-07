"""Regression guard for the design-token discipline in
docs/superpowers/specs/2026-08-31-刷题复盘系统-design.md: every colour in the
UI must trace back to design/tokens.css's semantic custom properties
(exposed to Tailwind via frontend/src/index.css's @theme block), never a
literal hex value hardcoded in a component. A stray `#c19a5c` silently
defeats the entire point of the token file -- changing the palette should
stay a one-line edit to design/build_palettes.py's CHOSEN palette, not a
grep-and-replace across every component that copied a hex code.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

SRC_DIR = Path(__file__).resolve().parent.parent / "frontend" / "src"

HEX_COLOR_RE = re.compile(r"#[0-9a-fA-F]{3,8}\b")

CHECKED_SUFFIXES = {".ts", ".tsx", ".css"}

# frontend/src/styles/tokens.generated.css is the one file allowed to hold
# literal hex values: it's an auto-generated, gitignored copy of
# design/tokens.css itself (see vite.config.ts's syncDesignTokens plugin),
# regenerated on every `npm run dev`/`npm run build`. Every other file
# under src/ is expected to reference its custom properties by name
# (var(--panel), or the Tailwind utility classes built from them) instead.
EXEMPT_RELATIVE_PATHS = {Path("styles") / "tokens.generated.css"}


def test_no_hex_color_literals_in_frontend_src():
    if not SRC_DIR.is_dir():
        pytest.skip(f"{SRC_DIR} does not exist")

    offenders: dict[str, list[str]] = {}
    for path in SRC_DIR.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(SRC_DIR)
        if relative in EXEMPT_RELATIVE_PATHS or path.suffix not in CHECKED_SUFFIXES:
            continue

        found = HEX_COLOR_RE.findall(path.read_text(encoding="utf-8"))
        if found:
            offenders[str(relative)] = found

    assert offenders == {}, (
        "hex colour literal(s) found under frontend/src -- reference a "
        "design/tokens.css semantic name instead (e.g. the Tailwind "
        f"utility classes bg-panel / text-text-bright / border-border): {offenders}"
    )
