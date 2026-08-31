from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from sqlmodel import Session, select

from leetcode_helper.models import Template, Topic
from leetcode_helper.repositories.today import get_today_view

router = APIRouter()


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
        template_codes = [
            row.code
            for row in session.exec(
                select(Template).where(Template.topic_id == topic.id).order_by(Template.code)
            ).all()
        ]
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
