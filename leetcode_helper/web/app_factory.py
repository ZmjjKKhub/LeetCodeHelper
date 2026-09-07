"""FastAPI 应用装配。engine 与「今天是哪天」都可注入，方便测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy import Engine

from leetcode_helper.api import router as api_router
from leetcode_helper.db import get_engine
from leetcode_helper.repositories.today import NoActiveTopic

# The React SPA's build output (spec C5: FastAPI static-serves the
# frontend/dist Vite build; still one process). Not committed --
# frontend/dist is gitignored -- so this may not exist on a fresh clone
# that hasn't run `npm run build` yet; create_app() below checks
# .is_dir() at app-build time rather than assuming it's there. Module
# level (not a local in create_app) so tests can monkeypatch it to
# exercise the "not built yet" branch without actually deleting anything.
FRONTEND_DIST_DIR = Path(__file__).resolve().parent.parent.parent / "frontend" / "dist"


def create_app(
    *,
    engine: Engine | None = None,
    today_provider: Callable[[], date] | None = None,
) -> FastAPI:
    app = FastAPI(title="刷题复盘系统")
    app.state.engine = engine if engine is not None else get_engine()
    app.state.today_provider = today_provider if today_provider is not None else date.today

    @app.get("/today", include_in_schema=False)
    def redirect_today() -> RedirectResponse:
        # /today was the old Jinja page's URL. The React app's Today page now
        # lives at "/" -- redirect old bookmarks/links there instead of
        # letting the request fall through to the SPA catch-all below (which
        # would serve index.html at a URL the app itself never routes to,
        # since App.tsx has no "/today" route -- React Router's own
        # `<Route path="*">` would then bounce it to "/" client-side anyway,
        # but a server-side redirect gets there in one hop instead of two).
        return RedirectResponse("/")

    @app.exception_handler(NoActiveTopic)
    def no_topic_configured(request: Request, exc: NoActiveTopic) -> JSONResponse:
        # NoActiveTopic means "no active topic exists" -- most commonly
        # because the seed importer has never been run. That is an expected,
        # recoverable state for a fresh install, not a bug: surface it as a
        # 503 JSON body (the only kind of client left is the React
        # frontend's own fetch calls under /api/*) instead of letting
        # FastAPI turn it into an unhandled 500 with a raw stack trace.
        #
        # This handler is registered on NoActiveTopic specifically, *not* the
        # bare LookupError it subclasses. LookupError is also the base class
        # of KeyError and IndexError, so catching it broadly would silently
        # relabel unrelated internal bugs (e.g. a raw dict/list subscript
        # error anywhere in the request) as "you forgot to seed" and destroy
        # their traceback.
        return JSONResponse({"detail": str(exc)}, status_code=503)

    app.include_router(api_router, prefix="/api")

    # React SPA, mounted last on purpose. Starlette resolves a request
    # against its route list in registration order and stops at the first
    # match -- /today, the /api/* router, and the /assets mount below are
    # all registered first, so none of them can ever be shadowed by the
    # catch-all `{full_path:path}` route added here. It only ever fires
    # for a path none of those already claimed -- including "/" and
    # "/history", both of which the React app itself routes client-side.
    if FRONTEND_DIST_DIR.is_dir():
        app.mount(
            "/assets",
            StaticFiles(directory=str(FRONTEND_DIST_DIR / "assets")),
            name="frontend-assets",
        )
        index_html = FRONTEND_DIST_DIR / "index.html"

        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_catch_all(full_path: str) -> FileResponse:
            return FileResponse(index_html)
    else:
        # A fresh clone (or one where `npm run build` in frontend/ just
        # hasn't been run yet) must still start and say something a person
        # can act on -- not crash at mount time (StaticFiles raises if its
        # directory is missing) and not a bare 404/500 on every route the
        # SPA would otherwise serve. Mirrors app.py's own "migrations
        # haven't run yet" message for the same reason.
        @app.get("/{full_path:path}", include_in_schema=False)
        def spa_not_built(full_path: str) -> HTMLResponse:
            return HTMLResponse(
                "<h1>前端还没有构建</h1>"
                "<p>请先执行：</p>"
                "<pre>cd frontend\nnpm install\nnpm run build</pre>"
                "<p>然后重新运行 <code>uv run app.py</code>。"
                "（/api/* 这些 JSON 接口不受影响，可以照常使用。）</p>",
                status_code=503,
            )

    return app
