from __future__ import annotations

import html
from datetime import date as date_type

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from leetcode_helper.models import DurationBucket, Mark
from leetcode_helper.repositories.attempts import ProblemNotFound, record_attempt
from leetcode_helper.repositories.today import (
    active_topic,
    get_problem_item,
    get_today_view,
    list_template_codes,
)
from leetcode_helper.services.attempts import AttemptInput

router = APIRouter()


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request) -> HTMLResponse:
    app = request.app
    today = app.state.today_provider()
    with Session(app.state.engine) as session:
        topic = active_topic(session)
        view = get_today_view(session, topic_id=topic.id, today=today)
        template_codes = list_template_codes(session, topic.id)
        return app.state.templates.TemplateResponse(
            request,
            "today.html",
            {
                "topic": topic,
                "today": today,
                "view": view,
                "template_codes": template_codes,
            },
        )


def _error_row_response(
    app,
    request: Request,
    session: Session,
    *,
    problem_id: int,
    error: str,
    status_code: int,
) -> HTMLResponse:
    """Render a validation/lookup failure as an HTML fragment.

    The client's hx-target is a fixed "#problem-{id}" selector baked into the
    form that was submitted, independent of whatever we return -- so the
    fragment must carry a matching id or a future swap onto this row breaks.
    Returning HTMLResponse/TemplateResponse here (never HTTPException) matters
    because HTTPException's default body is application/json: HTMX would
    either dump that raw JSON into the page on a swap, or -- since HTMX does
    not swap non-2xx responses by default -- silently do nothing, leaving the
    user with no feedback at all. An HTML fragment, scoped to the row and
    carrying a readable message, is what base.html's htmx:beforeSwap hook
    opts into swapping for 404/422 responses on this endpoint.

    `problem_id` here is always the int FastAPI already coerced via
    `Form(...)` on the caller's signature -- never raw user text -- so
    embedding it directly in the fallback fragment's id/text is safe.
    `error`, however, is a message string and is HTML-escaped before use.
    """
    try:
        item = get_problem_item(session, problem_id)
        template_codes = list_template_codes(session, item.problem.topic_id)
    except Exception:
        # Either the problem itself doesn't exist (ProblemNotFound) or
        # building a full row failed for some other repository-layer reason
        # -- e.g. a corrupt topic.config_json (TopicConfigError, a ValueError
        # subclass) raising a *second* time while we try to redisplay the
        # row after the *first* raise already produced `error`. Either way,
        # rendering the error page itself must never become an unhandled
        # 500; fall back to a minimal fragment carrying the original message.
        return HTMLResponse(
            f'<article id="problem-{problem_id}" class="problem-row">'
            f'<p class="error">保存失败：{html.escape(error)}</p></article>',
            status_code=status_code,
        )

    return app.state.templates.TemplateResponse(
        request,
        "partials/_problem_row.html",
        {"item": item, "template_codes": template_codes, "error": error},
        status_code=status_code,
    )


@router.post("/attempts", response_class=HTMLResponse)
def create_attempt(
    request: Request,
    problem_id: int = Form(...),
    duration_bucket: DurationBucket = Form(...),
    mark: Mark = Form(...),
    submit_count: int = Form(1),
    used_template: str = Form(""),
    duration_sec: int | None = Form(None),
) -> HTMLResponse:
    app = request.app
    today: date_type = app.state.today_provider()

    with Session(app.state.engine) as session:
        try:
            attempt = record_attempt(
                session,
                AttemptInput(
                    problem_id=problem_id,
                    duration_bucket=duration_bucket,
                    mark=mark,
                    submit_count=submit_count,
                    used_template=used_template or None,
                    duration_sec=duration_sec,
                ),
                today=today,
            )
        except ProblemNotFound as exc:
            return _error_row_response(
                app, request, session, problem_id=problem_id, error=str(exc), status_code=404
            )
        except ValueError as exc:
            return _error_row_response(
                app, request, session, problem_id=problem_id, error=str(exc), status_code=422
            )

        item = get_problem_item(session, problem_id, attempt=attempt)
        # template_codes=[] is safe here only because a done item (item.attempt
        # is set) never renders the <form>/<select> branch that reads
        # template_codes -- see partials/_problem_row.html's `{% if not
        # item.is_done %}` guard.
        return app.state.templates.TemplateResponse(
            request,
            "partials/_problem_row.html",
            {"item": item, "template_codes": []},
        )
