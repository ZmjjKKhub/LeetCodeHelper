"""GET /api/meta."""

from __future__ import annotations

from sqlmodel import Session

from leetcode_helper.models import Template
from leetcode_helper.services.attempts import OUTCOME_CONSEQUENCES, OUTCOME_LABELS, Outcome
from tests.conftest import make_client, seed

_SIX_TEMPLATE_CODES = ["A", "B", "C", "D", "E", "F"]


def test_api_meta_happy_path_shape(engine):
    topic_id, _ = seed(engine, with_plan=False)
    with Session(engine) as session:
        for code in _SIX_TEMPLATE_CODES:
            session.add(
                Template(
                    topic_id=topic_id,
                    code=code,
                    name=f"模板{code}",
                    trigger_signal=f"信号{code}",
                )
            )
        session.commit()

    response = make_client(engine).get("/api/meta")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    body = response.json()

    assert body["topic"] == {"code": "sliding-window", "name": "滑动窗口"}

    # All six templates, in code order, each carrying code/name/trigger_signal.
    assert [t["code"] for t in body["templates"]] == _SIX_TEMPLATE_CODES
    assert body["templates"][0] == {"code": "A", "name": "模板A", "trigger_signal": "信号A"}

    # All four outcomes, each with its label and review consequence, sourced
    # from services.attempts.OUTCOME_LABELS / OUTCOME_CONSEQUENCES -- the
    # single source of truth the Jinja page's own filters read from too.
    assert len(body["outcomes"]) == 4
    by_value = {o["value"]: o for o in body["outcomes"]}
    for outcome in Outcome:
        assert by_value[outcome.value]["label"] == OUTCOME_LABELS[outcome]
        assert by_value[outcome.value]["consequence"] == OUTCOME_CONSEQUENCES[outcome]

    assert by_value["within_solid"]["consequence"] == "不排复习"
    assert by_value["unsolved"]["consequence"] == "复习 4 轮（D+1、D+3、D+7、D+14）"


def test_api_meta_no_active_topic_is_503_json(engine):
    response = make_client(engine).get("/api/meta")
    assert response.status_code == 503
    assert response.headers["content-type"].startswith("application/json")
    assert "detail" in response.json()
