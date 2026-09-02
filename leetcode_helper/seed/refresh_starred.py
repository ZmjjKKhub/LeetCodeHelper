"""用 LeetCode 账号的收藏状态刷新 problems.yaml 的 is_starred。

用法：

    LEETCODE_SESSION=<你的 cookie> uv run python -m leetcode_helper.seed.refresh_starred \
        data/topics/sliding-window

`is_starred` 的语义是「我在 LeetCode 上收藏（star）了这道题」。这个信息拿不到
离线来源——它是账号状态，只能带登录 cookie 向官方接口要。接口 `/api/problems/all/`
每条记录里的 `is_favor` 就是它，匿名请求下恒为 false。

这是一次性的刷新脚本，不是常驻功能（规格 §8 把 LeetCode 抓取降级成了一次性脚本）：
收藏会变，想同步就重跑一次，然后把 problems.yaml 的改动提交掉。

关于 cookie：只从环境变量读，不落盘、不打印、不写进任何日志或报错信息。
拿法是浏览器登录 leetcode.cn 后，开发者工具 → Application → Cookies →
复制 `LEETCODE_SESSION` 的值。它等同于你的登录态，别贴进聊天记录或提交进仓库。
"""

from __future__ import annotations

import json
import os
import re
import sys
import urllib.error
import urllib.request
from pathlib import Path

API_URL = "https://leetcode.cn/api/problems/all/"
SESSION_ENV = "LEETCODE_SESSION"

# 逐块改写而不是 yaml.safe_dump 整份重写：problems.yaml 顶部有一段说明每一列
# 来源的注释，条目之间也靠空行分隔。整份 dump 会把注释和排版全抹掉，而这份
# 文件是要人读、要进 code review 的。
_LC_ID = re.compile(r"^\s*- lc_id:\s*(\d+)\s*$", re.M)
_IS_STARRED = re.compile(r"^(\s*is_starred:\s*)(true|false)\s*$", re.M)


class RefreshError(RuntimeError):
    """刷新失败。消息里不会包含 cookie。"""


def fetch_favorites(session_cookie: str) -> dict[int, bool]:
    """返回 {力扣题号: 是否已收藏}。

    只解析 `frontend_question_id` 是纯数字的条目——接口里混着 "LCP 82"、
    "剑指 Offer 03" 这类非数字题号，它们不属于本系统的题库。
    """
    request = urllib.request.Request(
        API_URL,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Cookie": f"{SESSION_ENV}={session_cookie}",
            "Referer": "https://leetcode.cn/problemset/all/",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RefreshError(f"接口返回 {exc.code}，cookie 可能已过期") from None
    except urllib.error.URLError as exc:
        raise RefreshError(f"请求失败: {exc.reason}") from None

    favorites: dict[int, bool] = {}
    for entry in payload.get("stat_status_pairs", []):
        raw_id = str(entry["stat"].get("frontend_question_id", "")).strip()
        if raw_id.isdigit():
            favorites[int(raw_id)] = bool(entry.get("is_favor"))
    if not favorites:
        raise RefreshError("接口没有返回任何题目，格式可能变了")
    return favorites


def apply_favorites(text: str, favorites: dict[int, bool]) -> tuple[str, list[int], list[int]]:
    """把收藏状态写进 problems.yaml 的文本，返回 (新文本, 改动的题号, 接口里查不到的题号)。"""
    changed: list[int] = []
    missing: list[int] = []
    blocks = text.split("\n\n")

    for index, block in enumerate(blocks):
        match = _LC_ID.search(block)
        if match is None:
            continue
        lc_id = int(match.group(1))
        if lc_id not in favorites:
            missing.append(lc_id)
            continue

        wanted = "true" if favorites[lc_id] else "false"
        replaced, count = _IS_STARRED.subn(rf"\g<1>{wanted}", block)
        if count == 0:
            raise RefreshError(f"lc_id={lc_id} 的条目里没有 is_starred 字段")
        if replaced != block:
            changed.append(lc_id)
            blocks[index] = replaced

    return "\n\n".join(blocks), changed, missing


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print(
            "用法: LEETCODE_SESSION=<cookie> python -m leetcode_helper.seed.refresh_starred "
            "<topic_dir>",
            file=sys.stderr,
        )
        return 2

    session_cookie = os.environ.get(SESSION_ENV, "").strip()
    if not session_cookie:
        print(
            f"缺少环境变量 {SESSION_ENV}。\n"
            "浏览器登录 leetcode.cn 后，开发者工具 → Application → Cookies，\n"
            f"复制 {SESSION_ENV} 的值。它等同于登录态，别提交进仓库。",
            file=sys.stderr,
        )
        return 2

    path = Path(argv[1]) / "problems.yaml"
    if not path.exists():
        print(f"找不到 {path}", file=sys.stderr)
        return 1

    try:
        favorites = fetch_favorites(session_cookie)
    except RefreshError as exc:
        print(f"刷新失败：{exc}", file=sys.stderr)
        return 1

    text = path.read_text(encoding="utf-8")
    updated, changed, missing = apply_favorites(text, favorites)

    starred_total = sum(1 for lc_id in favorites if favorites[lc_id])
    if starred_total == 0:
        print(
            "接口返回的收藏数为 0——通常意味着 cookie 没生效（过期或复制错了），\n"
            "而不是你真的一道题都没收藏。未改动任何文件。",
            file=sys.stderr,
        )
        return 1

    path.write_text(updated, encoding="utf-8")

    now_starred = sorted(
        int(_LC_ID.search(b).group(1))
        for b in updated.split("\n\n")
        if _LC_ID.search(b) and re.search(r"is_starred:\s*true", b)
    )
    print(f"你的账号共收藏 {starred_total} 道题。")
    print(f"本题库改动 {len(changed)} 条：{changed if changed else '无'}")
    print(f"当前标星：{now_starred if now_starred else '无'}")
    if missing:
        print(f"接口里查不到的题号（已跳过）：{missing}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
