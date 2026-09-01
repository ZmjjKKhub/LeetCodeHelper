"""FastAPI 应用装配。engine 与「今天是哪天」都可注入，方便测试。"""

from __future__ import annotations

import html
from datetime import date
from pathlib import Path
from typing import Callable

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy import Engine
from sqlmodel import Session

from leetcode_helper.db import get_engine
from leetcode_helper.models import DurationBucket
from leetcode_helper.repositories.today import NoActiveTopic, get_problem_item, list_template_options
from leetcode_helper.web.routes import history as history_routes
from leetcode_helper.web.routes import today as today_routes

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
STATIC_DIR = Path(__file__).resolve().parent / "static"

# Chinese display labels for DurationBucket. Kept here (next to format_limit,
# the other display-formatting helper) rather than in a route module: a
# route only handles one page, but this label is a property of the enum
# itself and any page rendering an Attempt needs it consistently.
#
# Keyed by the enum member (not `.value`) and asserted complete against
# `DurationBucket` below -- a route-local `dict[str, str]` keyed by `.value`
# has no such check, so adding a new bucket to the enum without updating the
# dict would silently raise KeyError mid-render the first time that bucket
# was actually hit, instead of failing loudly at import time.
BUCKET_LABELS: dict[DurationBucket, str] = {
    DurationBucket.within: "限时内",
    DurationBucket.over: "超时",
    DurationBucket.unsolved: "没做出来",
}
assert set(BUCKET_LABELS) == set(DurationBucket), "BUCKET_LABELS 未覆盖所有 DurationBucket 枚举值"


def format_limit(seconds: int) -> str:
    return f"{seconds // 60:02d}:{seconds % 60:02d}"


def format_bucket(bucket: DurationBucket) -> str:
    return BUCKET_LABELS[bucket]


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
    templates.env.filters["bucket_label"] = format_bucket
    app.state.templates = templates

    app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse("/today")

    @app.exception_handler(NoActiveTopic)
    def no_topic_configured(request: Request, exc: NoActiveTopic) -> HTMLResponse:
        # NoActiveTopic means "no active topic exists" -- most commonly
        # because the seed importer has never been run. That is an expected,
        # recoverable state for a fresh install, not a bug: surface it as a
        # plain explanatory page (503, since the service genuinely has
        # nothing to serve yet) instead of letting FastAPI turn it into an
        # unhandled 500 with a raw stack trace.
        #
        # This handler is registered on NoActiveTopic specifically, *not* the
        # bare LookupError it subclasses. LookupError is also the base class
        # of KeyError and IndexError, so catching it broadly would silently
        # relabel unrelated internal bugs (e.g. a raw dict/list subscript
        # error anywhere in the request) as "you forgot to seed" and destroy
        # their traceback.
        return HTMLResponse(
            f"<h1>还没有可用的专题</h1><p>{html.escape(str(exc))}</p>",
            status_code=503,
        )

    @app.exception_handler(RequestValidationError)
    async def form_validation_error(request: Request, exc: RequestValidationError) -> HTMLResponse:
        # A bogus enum value (e.g. mark="Z") or a missing/non-numeric
        # problem_id fails FastAPI/Pydantic's own Form(...) coercion *before*
        # the route body runs -- routes/today.py's own try/except around
        # record_attempt never sees it. Left to FastAPI's default, this would
        # be a JSON body, which for an HTMX-driven fragment endpoint is
        # either dumped raw into the page on swap or silently dropped.
        if request.url.path != "/attempts":
            return HTMLResponse(
                f"<h1>请求参数错误</h1><p>{html.escape(str(exc))}</p>", status_code=422
            )

        # Recover the raw submitted problem_id ourselves so we can still
        # target and re-render the failed row -- but only trust it if it is
        # purely digits. This handler reads the form directly, bypassing the
        # int coercion Form(...) would normally have done, so an
        # attacker-controlled value could otherwise flow straight into an
        # HTML attribute/id (a real reflected-injection probe, not
        # theoretical: `problem_id='"><script>alert(1)</script>'` used to
        # come back live in the response body).
        problem_id: int | None = None
        try:
            form = await request.form()
            raw = form.get("problem_id")
            if raw is not None and str(raw).isdigit():
                problem_id = int(str(raw))
        except Exception:
            pass

        if problem_id is not None:
            with Session(app.state.engine) as session:
                try:
                    item = get_problem_item(session, problem_id)
                    template_options = list_template_options(session, item.problem.topic_id)
                except Exception:
                    item = None
                if item is not None:
                    return app.state.templates.TemplateResponse(
                        request,
                        "partials/_problem_row.html",
                        {
                            "item": item,
                            "template_options": template_options,
                            "error": "提交的数据不合法，请重新选择后再试",
                        },
                        status_code=422,
                    )

        # No usable problem_id to key a row off of (missing, non-numeric, or
        # a problem that no longer exists) -- there is no real #problem-N
        # element we could safely target, so don't fabricate one. Surface a
        # page-level notice instead of silently doing nothing.
        return HTMLResponse(
            '<p class="error">保存失败：提交的数据不合法，请刷新页面后重试</p>',
            status_code=422,
        )

    app.include_router(today_routes.router)
    app.include_router(history_routes.router)
    return app
