"""FastAPI 应用装配。engine 与「今天是哪天」都可注入，方便测试。"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine

from leetcode_helper.db import get_engine
from leetcode_helper.web.routes import history as history_routes
from leetcode_helper.web.routes import today as today_routes

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


def format_limit(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def create_app(
    *,
    engine: Engine | None = None,
    today_provider: Callable[[], date] | None = None,
) -> FastAPI:
    app = FastAPI(title="刷题复盘系统")
    app.state.engine = engine if engine is not None else get_engine()
    app.state.today_provider = today_provider if today_provider is not None else date.today

    templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
    templates.env.filters["limit"] = format_limit
    app.state.templates = templates

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/today")

    @app.exception_handler(LookupError)
    def no_topic_configured(request: Request, exc: LookupError) -> HTMLResponse:
        # A LookupError here means "no active topic exists" -- most commonly
        # because the seed importer has never been run. That is an expected,
        # recoverable state for a fresh install, not a bug: surface it as a
        # plain explanatory page (503, since the service genuinely has
        # nothing to serve yet) instead of letting FastAPI turn it into an
        # unhandled 500 with a raw stack trace.
        return HTMLResponse(
            f"<h1>还没有可用的专题</h1><p>{exc}</p>",
            status_code=503,
        )

    app.include_router(today_routes.router)
    app.include_router(history_routes.router)
    return app
