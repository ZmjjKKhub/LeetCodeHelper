"""GET /api/history."""

from __future__ import annotations

from fastapi import APIRouter, Query, Request
from sqlmodel import Session

from leetcode_helper.repositories.attempts import list_history
from leetcode_helper.repositories.today import active_topic

from ..converters import to_history_row_out
from ..schemas import HistoryOut

router = APIRouter()

# list_history caps at this many rows. A silent truncation with no
# indication would be a bad failure mode -- the response instead reports the
# count it returned and, when the cap was hit, an explicit `truncated` flag
# so the frontend can say older attempts exist but aren't shown, instead of
# just quietly dropping them.
HISTORY_LIMIT = 500


@router.get("/history", response_model=HistoryOut)
def api_history(
    request: Request,
    limit: int = Query(default=HISTORY_LIMIT, ge=1),
) -> HistoryOut:
    app = request.app
    with Session(app.state.engine) as session:
        topic = active_topic(session)  # NoActiveTopic -> app-level 503 JSON handler
        rows = list_history(session, topic_id=topic.id, limit=limit)
        return HistoryOut(
            rows=[to_history_row_out(row) for row in rows],
            limit=limit,
            truncated=len(rows) == limit,
        )
