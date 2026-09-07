"""GET /api/progress.

Exists because neither /api/today nor /api/history exposes the topic's full
problem catalogue -- see leetcode_helper/repositories/progress.py's module
docstring for why their union is only exact in fallback mode. The 今日页 progress
panel (design/Main.dc.html) needs one cell per problem in the topic, plus the
plan's day-N-of-M position, in a single call.
"""

from __future__ import annotations

from datetime import date as date_type

from fastapi import APIRouter, Query, Request
from sqlmodel import Session

from leetcode_helper.repositories.progress import get_progress_view
from leetcode_helper.repositories.today import active_topic

from ..converters import to_progress_out
from ..schemas import ProgressOut

router = APIRouter()


@router.get("/progress", response_model=ProgressOut)
def api_progress(
    request: Request,
    date: date_type | None = Query(default=None, description="YYYY-MM-DD, defaults to today"),
) -> ProgressOut:
    app = request.app
    today = date if date is not None else app.state.today_provider()
    with Session(app.state.engine) as session:
        topic = active_topic(session)  # NoActiveTopic -> app-level 503 JSON handler
        view = get_progress_view(session, topic_id=topic.id, today=today)
        return to_progress_out(topic, view)
