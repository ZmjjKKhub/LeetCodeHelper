"""入口：uv run app.py

`import app` must be side-effect free. The plan's original version called
create_app() at module import time, which means simply *importing* this
module -- exactly what its own test suite does -- connects to the real
data/app.db as a side effect. Instead, the app is only built inside
build_app()/main(), never at import time. uvicorn.run() is called with the
already-built app *object* (not a "module:attr" string), so no module-level
ASGI attribute is required for uvicorn's sake either.
"""

from __future__ import annotations

import socket
import sys
import threading
import time
import webbrowser

import uvicorn
from sqlalchemy import Engine, inspect

from leetcode_helper.db import get_engine
from leetcode_helper.web.app_factory import create_app

HOST = "127.0.0.1"
PORT = 8765

# A fresh clone (or a real db file that predates any `alembic upgrade head`)
# has no tables at all. Without a check, the first request to hit /today
# would blow up with an unhandled `OperationalError: no such table: topic`
# -- a terrible first impression for a new install. Probing one
# representative table is enough to distinguish "never migrated" from
# "properly initialized"; a full schema diff isn't warranted here.
_MARKER_TABLE = "topic"


def build_app(engine: Engine | None = None):
    """Build the ASGI app. Deferred to call time -- see module docstring."""
    return create_app(engine=engine)


def _ensure_schema_ready(engine: Engine) -> bool:
    return inspect(engine).has_table(_MARKER_TABLE)


def _port_is_open(host: str, port: int, timeout: float = 0.2) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        return sock.connect_ex((host, port)) == 0


def _open_browser_when_ready(
    host: str, port: int, url: str, *, attempts: int = 20, interval: float = 0.25
) -> None:
    """Poll until the server is actually accepting connections before
    opening a browser tab.

    The plan's version used `threading.Timer(1.0, ...)`: a fixed delay that
    opens the browser regardless of whether the server actually started.
    If PORT was already taken (another instance running, some other
    process squatting on it), the user gets a browser tab pointed at
    nothing while uvicorn fails to bind in the background. Polling for the
    port to actually be open -- and giving up quietly if it never is --
    avoids that.
    """
    for _ in range(attempts):
        if _port_is_open(host, port):
            webbrowser.open(url)
            return
        time.sleep(interval)
    # Gave up: the server never came up (e.g. the port was already taken).
    # Don't open a browser tab onto nothing.


def main() -> None:
    engine = get_engine()
    if not _ensure_schema_ready(engine):
        print(
            "数据库还没有初始化，看起来 migrations 还没跑过。请先执行：\n"
            "  uv run alembic upgrade head\n"
            "  uv run python -m leetcode_helper.seed data/topics/sliding-window\n"
            "然后重新运行 uv run app.py。",
            file=sys.stderr,
        )
        sys.exit(1)

    app = build_app(engine=engine)
    threading.Thread(
        target=_open_browser_when_ready,
        args=(HOST, PORT, f"http://{HOST}:{PORT}/"),
        daemon=True,
    ).start()
    uvicorn.run(app, host=HOST, port=PORT, log_level="info")


if __name__ == "__main__":
    main()
