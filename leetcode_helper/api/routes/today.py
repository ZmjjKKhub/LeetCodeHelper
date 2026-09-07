"""GET /api/today, POST /api/attempts."""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, HTTPException, Query, Request
from sqlmodel import Session

from leetcode_helper.repositories.attempts import ProblemNotFound, record_attempt
from leetcode_helper.repositories.today import active_topic, get_problem_item, get_today_view
from leetcode_helper.services.attempts import AttemptInput, split_outcome

from ..converters import to_today_item_out, to_today_out
from ..schemas import AttemptCreateIn, TodayItemOut, TodayOut

router = APIRouter()


@router.get("/today", response_model=TodayOut)
def api_today(
    request: Request,
    date: date_type | None = Query(default=None, description="YYYY-MM-DD, defaults to today"),
) -> TodayOut:
    app = request.app
    today = date if date is not None else app.state.today_provider()
    with Session(app.state.engine) as session:
        topic = active_topic(session)  # NoActiveTopic -> app-level 503 JSON handler
        view = get_today_view(session, topic_id=topic.id, today=today)
        return to_today_out(topic, today, view)


@router.post("/attempts", response_model=TodayItemOut)
def api_create_attempt(request: Request, body: AttemptCreateIn) -> TodayItemOut:
    app = request.app
    today: date_type = app.state.today_provider()

    # Split-at-the-boundary rule: AttemptInput/build_attempt/the repository
    # never learn about Outcome, only duration_bucket + mark.
    duration_bucket, mark = split_outcome(body.outcome)

    with Session(app.state.engine) as session:
        try:
            attempt = record_attempt(
                session,
                AttemptInput(
                    problem_id=body.problem_id,
                    duration_bucket=duration_bucket,
                    mark=mark,
                    submit_count=body.submit_count,
                    used_template=body.used_template or None,
                ),
                today=today,
            )
        except ProblemNotFound as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        item = get_problem_item(session, body.problem_id, attempt=attempt)
        return to_today_item_out(item)
