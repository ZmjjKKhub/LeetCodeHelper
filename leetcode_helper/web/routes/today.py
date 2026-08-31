from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Form, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from leetcode_helper.models import DurationBucket, Mark, Problem, Template, Topic
from leetcode_helper.repositories.attempts import record_attempt
from leetcode_helper.repositories.today import TodayItem, get_today_view
from leetcode_helper.services.attempts import AttemptInput
from leetcode_helper.services.topics import parse_topic_config_json, time_limit_for

router = APIRouter()


def _template_codes(session: Session, topic_id: int) -> list[str]:
    return [
        row.code
        for row in session.exec(
            select(Template).where(Template.topic_id == topic_id).order_by(Template.code)
        ).all()
    ]


def active_topic(session: Session) -> Topic:
    # is_active == True (not `.is_active`) is required here: SQLModel/SQLAlchemy
    # column comparisons build a SQL WHERE clause, whereas a plain truthy
    # attribute access on the class does not filter anything.
    topic = session.exec(select(Topic).where(Topic.is_active == True).order_by(Topic.id)).first()  # noqa: E712
    if topic is None:
        raise LookupError("还没有导入任何 topic，先跑 python -m leetcode_helper.seed")
    return topic


@router.get("/today", response_class=HTMLResponse)
def today_page(request: Request) -> HTMLResponse:
    app = request.app
    today = app.state.today_provider()
    with Session(app.state.engine) as session:
        topic = active_topic(session)
        view = get_today_view(session, topic_id=topic.id, today=today)
        template_codes = _template_codes(session, topic.id)
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
    opts into swapping for 404/422 responses.
    """
    problem = session.get(Problem, problem_id)
    if problem is None:
        # We don't even have a Problem to re-render a real row around (e.g. a
        # stale/forged problem_id). Fall back to a minimal fragment that at
        # least keeps the same id so the DOM node HTMX is about to target
        # still exists afterwards.
        return HTMLResponse(
            f'<article id="problem-{problem_id}" class="problem-row">'
            f'<p class="error">保存失败：{error}</p></article>',
            status_code=status_code,
        )

    topic = session.get(Topic, problem.topic_id)
    config = parse_topic_config_json(topic.config_json)
    item = TodayItem(problem=problem, time_limit_sec=time_limit_for(config, problem.difficulty))
    return app.state.templates.TemplateResponse(
        request,
        "partials/_problem_row.html",
        {
            "item": item,
            "template_codes": _template_codes(session, topic.id),
            "error": error,
        },
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
        except LookupError as exc:
            return _error_row_response(
                app, request, session, problem_id=problem_id, error=str(exc), status_code=404
            )
        except ValueError as exc:
            return _error_row_response(
                app, request, session, problem_id=problem_id, error=str(exc), status_code=422
            )

        problem = session.get(Problem, problem_id)
        topic = session.get(Topic, problem.topic_id)
        config = parse_topic_config_json(topic.config_json)
        item = TodayItem(
            problem=problem,
            time_limit_sec=time_limit_for(config, problem.difficulty),
            attempt=attempt,
        )
        # template_codes=[] is safe here only because a done item (item.attempt
        # is set) never renders the <form>/<select> branch that reads
        # template_codes -- see partials/_problem_row.html's `{% if not
        # item.is_done %}` guard.
        return app.state.templates.TemplateResponse(
            request,
            "partials/_problem_row.html",
            {"item": item, "template_codes": []},
        )
