"""把 Main.dc.html / History.dc.html 的颜色抽成语义变量，生成多版配色。

结构已经定稿（方向一），只有配色在变。手抄四遍同一份标记必然漂移——
生成出来才能保证四版之间除了颜色以外一个像素都不差。
"""

from __future__ import annotations

import pathlib
import re
import sys

HERE = pathlib.Path(__file__).resolve().parent
NEWLINE = chr(10)

# 原始稿里的字面色 -> 语义名。ALERT 和 HARD 在原稿里是同一个色号，
# 但它们是两件事：ALERT 是「没做出来」这个状态，HARD 是困难难度。
# 拆开之后，配色版本才可能让难度用明度、只留一个警示色。
TOKENS: dict[str, str] = {
    "#16181d": "BG",
    "#1c1f26": "PANEL",
    "#1a1d23": "CARD",
    "#22262f": "SUBPANEL",
    "#282c35": "BORDER",
    "#343a46": "BORDER_STRONG",
    "#22262e": "BORDER_SOFT",
    "#2f3540": "BTN_BORDER",
    "#242832": "NAV_ACTIVE",
    "#dfe3ea": "TEXT",
    "#eef1f6": "TEXT_BRIGHT",
    "#a7aebc": "TEXT_SOFT",
    "#8b93a3": "MUTED",
    "#6b7382": "DIM",
    "#5f6878": "DIM2",
    "#262b34": "CELL_EMPTY",
    "#7d879a": "TODAY_RING",
    "#4fb0a4": "EASY",
    "#c3a05a": "MEDIUM",
    "#2a2620": "MED_CHIP_BG",
    "#3b6b5f": "SEL_BORDER",
    "#1e2a27": "SEL_BG",
    "#d18b86": "ALERT",
}

PALETTES: dict[str, dict[str, str]] = {
    # 现版精修：冷灰底，难度三个色相，强调色统一到同一 oklch 明度/彩度。
    "Main": {
        "BG": "#15171b", "PANEL": "#1b1e24", "CARD": "#191c21", "SUBPANEL": "#21252c",
        "BORDER": "#272b33", "BORDER_STRONG": "#333842", "BORDER_SOFT": "#212429",
        "BTN_BORDER": "#2e333c", "NAV_ACTIVE": "#232730",
        "TEXT": "#dfe3ea", "TEXT_BRIGHT": "#f0f3f8", "TEXT_SOFT": "#a6adb9",
        "MUTED": "#8a91a0", "DIM": "#6a7180", "DIM2": "#5e6573",
        "CELL_EMPTY": "#262a32", "TODAY_RING": "#7c8697",
        "EASY": "#57ac9e", "MEDIUM": "#bda067", "HARD": "#ca908b", "ALERT": "#ca908b",
        "MED_CHIP_BG": "#292520", "SEL_BORDER": "#3d6a5f", "SEL_BG": "#1d2825",
    },
    # 暖炭：偏棕的黑底，难度用大地色（鼠尾草 / 赭 / 陶土），整体最柔和。
    "Ember": {
        "BG": "#181613", "PANEL": "#1f1c18", "CARD": "#1c1a16", "SUBPANEL": "#26221c",
        "BORDER": "#2c2822", "BORDER_STRONG": "#3a352c", "BORDER_SOFT": "#24211c",
        "BTN_BORDER": "#332e27", "NAV_ACTIVE": "#29251e",
        "TEXT": "#e7e1d6", "TEXT_BRIGHT": "#f5f0e6", "TEXT_SOFT": "#b3aa9b",
        "MUTED": "#968c7c", "DIM": "#756c5e", "DIM2": "#675f53",
        "CELL_EMPTY": "#2b271f", "TODAY_RING": "#8a8072",
        "EASY": "#8fa76a", "MEDIUM": "#c19a5c", "HARD": "#c4826a", "ALERT": "#c4826a",
        "MED_CHIP_BG": "#2b2318", "SEL_BORDER": "#5a6b45", "SEL_BG": "#23281c",
    },
    # 素墨：难度完全不用色相，改用明度深浅；整份界面只剩一个彩色——警示色。
    # 这是最贴近「简约」的一版，代价是难度区分弱于色相。
    "Ink": {
        "BG": "#16171a", "PANEL": "#1c1e21", "CARD": "#1a1c1f", "SUBPANEL": "#212327",
        "BORDER": "#292b2f", "BORDER_STRONG": "#35383d", "BORDER_SOFT": "#222427",
        "BTN_BORDER": "#2f3236", "NAV_ACTIVE": "#24262a",
        "TEXT": "#e2e4e7", "TEXT_BRIGHT": "#f2f4f6", "TEXT_SOFT": "#a8abaf",
        "MUTED": "#8b8e93", "DIM": "#6c6f75", "DIM2": "#5f6268",
        "CELL_EMPTY": "#26282c", "TODAY_RING": "#7e828a",
        "EASY": "#6f757c", "MEDIUM": "#a9aeb5", "HARD": "#dfe3e8", "ALERT": "#c98a84",
        "MED_CHIP_BG": "#26282c", "SEL_BORDER": "#4a4e54", "SEL_BG": "#212327",
    },
    # 靛青：冷蓝底，强调色对比最高，最「屏幕感」。
    "Indigo": {
        "BG": "#14161e", "PANEL": "#1a1d27", "CARD": "#181b24", "SUBPANEL": "#1f2330",
        "BORDER": "#262b39", "BORDER_STRONG": "#333949", "BORDER_SOFT": "#202433",
        "BTN_BORDER": "#2c3141", "NAV_ACTIVE": "#222738",
        "TEXT": "#dde1ee", "TEXT_BRIGHT": "#eef1fa", "TEXT_SOFT": "#a3aac0",
        "MUTED": "#868da6", "DIM": "#666d85", "DIM2": "#5a6178",
        "CELL_EMPTY": "#242938", "TODAY_RING": "#79819c",
        "EASY": "#4fb3c4", "MEDIUM": "#c2a35f", "HARD": "#c98aa8", "ALERT": "#d0798c",
        "MED_CHIP_BG": "#282318", "SEL_BORDER": "#37697a", "SEL_BG": "#1b2830",
    },
}

# 已选定的配色。2026-09-07 定为暖炭：偏棕黑底 + 大地色难度，最柔和。
# 其余三版保留在 PALETTES 里作为记录，不再生成画板。
CHOSEN = "Ember"


def tokenize(text: str, *, is_history: bool) -> str:
    """把字面色换成 {{TOKEN}}。"""
    if is_history:
        # 历史页图例里的「困难」色块是难度色，不是状态色——先单独换掉，
        # 否则会和同色号的 ALERT 一起被替换，素墨版就无法让两者分开。
        text = text.replace(
            'background: #d18b86;"></span>困难',
            'background: {{HARD}};"></span>困难',
        )
    for literal, name in TOKENS.items():
        text = text.replace(literal, "{{%s}}" % name)
    return text


def render(template: str, palette: dict[str, str]) -> str:
    def sub(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in palette:
            raise KeyError(f"色板缺少 {name}")
        return palette[name]

    out = re.sub(r"\{\{([A-Z0-9_]+)\}\}", sub, template)
    leftover = re.findall(r"\{\{[^}]+\}\}", out)
    if leftover:
        raise AssertionError(f"仍有未替换的变量: {sorted(set(leftover))}")
    return out


def main() -> int:
    main_cache = HERE / "_main.template"
    hist_cache = HERE / "_history.template"
    if main_cache.exists() and hist_cache.exists():
        main_tpl = main_cache.read_text(encoding="utf-8")
        hist_tpl = hist_cache.read_text(encoding="utf-8")
    else:
        main_tpl = tokenize((HERE / "Main.dc.html").read_text(encoding="utf-8"), is_history=False)
        hist_tpl = tokenize((HERE / "History.dc.html").read_text(encoding="utf-8"), is_history=True)

    # 抽取是否彻底：模板里不该再剩任何字面色（#ffffff 是链接 hover，保留）。
    for label, tpl in (("Main", main_tpl), ("History", hist_tpl)):
        stray = {c for c in re.findall(r"#[0-9a-fA-F]{6}", tpl) if c != "#ffffff"}
        if stray:
            print(f"{label} 仍有未抽取的字面色: {sorted(stray)}", file=sys.stderr)
            return 1

    (HERE / "_main.template").write_text(main_tpl, encoding="utf-8")
    (HERE / "_history.template").write_text(hist_tpl, encoding="utf-8")

    palette = PALETTES[CHOSEN]

    (HERE / "Main.dc.html").write_text(render(main_tpl, palette), encoding="utf-8")
    (HERE / "History.dc.html").write_text(render(hist_tpl, palette), encoding="utf-8")
    print(f"wrote Main.dc.html / History.dc.html（{CHOSEN}）")

    # 前端要用的设计令牌。这些变量名就是设计稿里用的那一套，
    # 所以实现时不需要再从稿子里一个个抠色号——换配色也只改这一处。
    lines = [
        "/* 由 design/build_palettes.py 生成，勿手改。",
        f"   当前配色：{CHOSEN}。换配色改 build_palettes.py 的 CHOSEN 后重跑。 */",
        ":root {",
    ]
    for key in sorted(palette):
        lines.append(f"  --{key.lower().replace('_', '-')}: {palette[key]};")
    lines.append("}")
    (HERE / "tokens.css").write_text(NEWLINE.join(lines) + NEWLINE, encoding="utf-8")
    print("wrote tokens.css")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
