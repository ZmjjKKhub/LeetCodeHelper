"""历史列表页。"""

from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session

from leetcode_helper.repositories.attempts import list_history
from leetcode_helper.repositories.today import active_topic

router = APIRouter()

# list_history caps at this many rows. A silent truncation with no
# indication would be a bad failure mode -- the page instead shows the
# count it rendered and, when the cap was hit, an explicit note that older
# attempts exist but aren't shown, instead of just quietly dropping them.
HISTORY_LIMIT = 500


@router.get("/history", response_class=HTMLResponse)
def history_page(request: Request) -> HTMLResponse:
    app = request.app
    with Session(app.state.engine) as session:
        topic = active_topic(session)
        rows = list_history(session, topic_id=topic.id, limit=HISTORY_LIMIT)
        return app.state.templates.TemplateResponse(
            request,
            "history.html",
            {
                "topic": topic,
                "rows": rows,
                "limit": HISTORY_LIMIT,
                "truncated": len(rows) == HISTORY_LIMIT,
            },
        )
