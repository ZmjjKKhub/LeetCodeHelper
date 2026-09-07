"""GET /api/meta -- everything the UI needs that is not per-request."""

from __future__ import annotations

from fastapi import APIRouter, Request
from sqlmodel import Session

from leetcode_helper.repositories.today import active_topic, list_template_options
from leetcode_helper.services.attempts import OUTCOME_CONSEQUENCES, OUTCOME_LABELS, Outcome

from ..schemas import MetaOut, OutcomeOut, TemplateOut, TopicOut

router = APIRouter()


@router.get("/meta", response_model=MetaOut)
def api_meta(request: Request) -> MetaOut:
    app = request.app
    with Session(app.state.engine) as session:
        topic = active_topic(session)  # NoActiveTopic -> app-level 503 JSON handler
        templates = list_template_options(session, topic.id)
        return MetaOut(
            topic=TopicOut(code=topic.code, name=topic.name),
            templates=[
                TemplateOut(code=t.code, name=t.name, trigger_signal=t.trigger_signal)
                for t in templates
            ],
            outcomes=[
                OutcomeOut(
                    value=outcome.value,
                    label=OUTCOME_LABELS[outcome],
                    consequence=OUTCOME_CONSEQUENCES[outcome],
                )
                for outcome in Outcome
            ],
        )
