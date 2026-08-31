"""用法: uv run python -m leetcode_helper.seed data/topics/sliding-window"""

from __future__ import annotations

import sys
from pathlib import Path

from leetcode_helper.db import session_scope
from leetcode_helper.seed.bundle import SeedBundleError, load_bundle
from leetcode_helper.seed.importer import import_bundle


def main(argv: list[str]) -> int:
    if len(argv) != 2:
        print("用法: python -m leetcode_helper.seed <topic_dir>", file=sys.stderr)
        return 2

    topic_dir = Path(argv[1])
    try:
        bundle = load_bundle(topic_dir)
    except SeedBundleError as exc:
        print(f"种子数据校验失败，未写入任何数据：{exc}", file=sys.stderr)
        return 1

    with session_scope() as session:
        report = import_bundle(session, bundle)
    print(f"导入完成：{report.summary()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
