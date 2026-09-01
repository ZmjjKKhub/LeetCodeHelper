from datetime import date

import pytest
from sqlmodel import Session, SQLModel, create_engine, select

from leetcode_helper.models import (
    DayStatus,
    Difficulty,
    ItemStatus,
    Plan,
    PlanDay,
    PlanItem,
    Problem,
    Template,
    Topic,
)
from leetcode_helper.seed.bundle import (
    SeedBundle,
    SeedPlan,
    SeedPlanDay,
    SeedProblem,
    SeedTemplate,
)
from leetcode_helper.seed.importer import import_bundle
from leetcode_helper.services.topics import parse_topic_config


@pytest.fixture
def session():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as s:
        yield s


def make_bundle(*, problems, days, plan_start=date(2026, 9, 1), plan_name="滑动窗口计划") -> SeedBundle:
    config = parse_topic_config(
        {
            "code": "sliding-window",
            "name": "滑动窗口",
            "time_limits": {"easy": 480, "medium": 1200, "hard": 2100},
            "card_fields": [],
        }
    )
    return SeedBundle(
        config=config,
        problems=problems,
        templates=(
            SeedTemplate(
                code="C",
                name="不定长·求最短",
                language="python",
                content="while ...",
                pitfalls="",
                trigger_signal="",
            ),
        ),
        plan=SeedPlan(name=plan_name, start_date=plan_start, days=days),
    )


def problem(lc_id: int, title: str = "题目") -> SeedProblem:
    return SeedProblem(
        lc_id=lc_id,
        title=title,
        url=f"https://leetcode.cn/problems/{lc_id}/",
        difficulty=Difficulty.medium,
        section="§2.2",
        section_name="越长越合法",
        is_starred=False,
        is_premium=False,
        is_optional=False,
        default_template="C",
    )


def test_import_creates_everything(session):
    bundle = make_bundle(
        problems=(problem(209), problem(3)),
        days=(SeedPlanDay(day_index=1, phase="阶段一", theme="三步走", problem_lc_ids=(209, 3)),),
    )
    report = import_bundle(session, bundle)

    assert report.problems_created == 2
    assert report.problems_updated == 0
    assert session.exec(select(Topic)).one().code == "sliding-window"
    assert len(session.exec(select(Problem)).all()) == 2
    assert len(session.exec(select(Template)).all()) == 1

    day = session.exec(select(PlanDay)).one()
    assert day.planned_date == date(2026, 9, 1)
    assert len(session.exec(select(PlanItem)).all()) == 2


def test_planned_date_derives_from_day_index(session):
    bundle = make_bundle(
        problems=(problem(209),),
        days=(
            SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),
            SeedPlanDay(day_index=3, phase="", theme="", problem_lc_ids=()),
        ),
    )
    import_bundle(session, bundle)

    days = session.exec(select(PlanDay).order_by(PlanDay.day_index)).all()
    assert [d.planned_date for d in days] == [date(2026, 9, 1), date(2026, 9, 3)]


def test_reimport_is_idempotent_and_updates_in_place(session):
    first = make_bundle(
        problems=(problem(209, title="旧标题"),),
        days=(SeedPlanDay(day_index=1, phase="", theme="旧主题", problem_lc_ids=(209,)),),
    )
    import_bundle(session, first)

    second = make_bundle(
        problems=(problem(209, title="长度最小的子数组"), problem(3)),
        days=(SeedPlanDay(day_index=1, phase="", theme="新主题", problem_lc_ids=(209, 3)),),
    )
    report = import_bundle(session, second)

    assert report.problems_created == 1
    assert report.problems_updated == 1
    assert len(session.exec(select(Topic)).all()) == 1
    assert len(session.exec(select(Plan)).all()) == 1

    titles = {p.lc_id: p.title for p in session.exec(select(Problem)).all()}
    assert titles == {209: "长度最小的子数组", 3: "题目"}

    day = session.exec(select(PlanDay)).one()
    assert day.theme == "新主题"
    assert len(session.exec(select(PlanItem)).all()) == 2


# ---------------------------------------------------------------------------
# Additional coverage beyond the plan's three tests.
# ---------------------------------------------------------------------------


def test_reimport_preserves_user_recorded_progress(session):
    """re-import must update seed-owned fields but never clobber user-owned state:
    PlanItem.status, PlanDay.status/actual_date."""
    first = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="阶段一", theme="旧主题", problem_lc_ids=(209,)),),
    )
    import_bundle(session, first)

    day = session.exec(select(PlanDay)).one()
    item = session.exec(select(PlanItem)).one()
    day.status = DayStatus.done
    day.actual_date = date(2026, 9, 2)
    item.status = ItemStatus.done
    session.add(day)
    session.add(item)
    session.commit()

    second = make_bundle(
        problems=(problem(209, title="新标题"),),
        days=(SeedPlanDay(day_index=1, phase="阶段一", theme="新主题", problem_lc_ids=(209,)),),
    )
    import_bundle(session, second)

    session.refresh(day)
    session.refresh(item)
    assert day.theme == "新主题"  # seed-owned: updated
    assert day.status == DayStatus.done  # user-owned: untouched
    assert day.actual_date == date(2026, 9, 2)  # user-owned: untouched
    assert item.status == ItemStatus.done  # user-owned: untouched
    assert session.exec(select(Problem)).one().title == "新标题"  # seed-owned: updated


def test_reimport_does_not_reset_planned_date_shift(session):
    """planned_date is only derived at creation time; a future phase shifts it
    directly, and re-importing the same plan must not stomp that shift."""
    bundle = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    import_bundle(session, bundle)

    day = session.exec(select(PlanDay)).one()
    day.planned_date = date(2026, 9, 10)  # simulate a manual schedule shift
    session.add(day)
    session.commit()

    import_bundle(session, bundle)  # re-import unchanged bundle

    session.refresh(day)
    assert day.planned_date == date(2026, 9, 10)


def test_removal_drops_untouched_orphaned_plan_item(session):
    first = make_bundle(
        problems=(problem(209), problem(3)),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209, 3)),),
    )
    import_bundle(session, first)
    assert len(session.exec(select(PlanItem)).all()) == 2

    second = make_bundle(
        problems=(problem(209), problem(3)),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    report = import_bundle(session, second)

    items = session.exec(select(PlanItem)).all()
    assert len(items) == 1
    assert items[0].problem_id == session.exec(
        select(Problem).where(Problem.lc_id == 209)
    ).one().id
    assert report.plan_items_removed == 1


def test_removal_preserves_done_plan_item_when_dropped_from_list(session):
    first = make_bundle(
        problems=(problem(209), problem(3)),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209, 3)),),
    )
    import_bundle(session, first)

    item_3 = session.exec(
        select(PlanItem).join(Problem).where(Problem.lc_id == 3)
    ).one()
    item_3.status = ItemStatus.done
    session.add(item_3)
    session.commit()

    second = make_bundle(
        problems=(problem(209), problem(3)),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    report = import_bundle(session, second)

    items = session.exec(select(PlanItem)).all()
    assert len(items) == 2  # the done item is preserved, not deleted
    assert report.plan_items_removed == 0
    preserved = session.exec(
        select(PlanItem).join(Problem).where(Problem.lc_id == 3)
    ).one()
    assert preserved.status == ItemStatus.done


def test_removal_drops_untouched_orphaned_plan_day(session):
    first = make_bundle(
        problems=(problem(209),),
        days=(
            SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),
            SeedPlanDay(day_index=2, phase="", theme="", problem_lc_ids=()),
        ),
    )
    import_bundle(session, first)
    assert len(session.exec(select(PlanDay)).all()) == 2

    second = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    report = import_bundle(session, second)

    days = session.exec(select(PlanDay)).all()
    assert len(days) == 1
    assert days[0].day_index == 1
    assert report.plan_days_removed == 1


def test_removal_preserves_touched_plan_day(session):
    first = make_bundle(
        problems=(problem(209),),
        days=(
            SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),
            SeedPlanDay(day_index=2, phase="", theme="", problem_lc_ids=()),
        ),
    )
    import_bundle(session, first)

    day2 = session.exec(select(PlanDay).where(PlanDay.day_index == 2)).one()
    day2.actual_date = date(2026, 9, 2)
    session.add(day2)
    session.commit()

    second = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    report = import_bundle(session, second)

    days = session.exec(select(PlanDay)).all()
    assert len(days) == 2  # day 2 preserved because it carries user data
    assert report.plan_days_removed == 0
    preserved = session.exec(select(PlanDay).where(PlanDay.day_index == 2)).one()
    assert preserved.actual_date == date(2026, 9, 2)


def test_report_distinguishes_created_from_updated_rows():
    engine = create_engine("sqlite://")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        bundle = make_bundle(
            problems=(problem(209), problem(3)),
            days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209, 3)),),
        )
        first_report = import_bundle(session, bundle)
        assert first_report.plan_days_created == 1
        assert first_report.plan_days_updated == 0
        assert first_report.plan_items_created == 2
        assert first_report.plan_items_updated == 0
        assert first_report.templates_created == 1
        assert first_report.templates_updated == 0

        second_report = import_bundle(session, bundle)
        assert second_report.plan_days_created == 0
        assert second_report.plan_days_updated == 1
        assert second_report.plan_items_created == 0
        assert second_report.plan_items_updated == 2
        assert second_report.templates_created == 0
        assert second_report.templates_updated == 1


def test_template_content_updates_in_place(session):
    first = make_bundle(problems=(problem(209),), days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),))
    import_bundle(session, first)

    config = parse_topic_config(
        {
            "code": "sliding-window",
            "name": "滑动窗口",
            "time_limits": {"easy": 480, "medium": 1200, "hard": 2100},
            "card_fields": [],
        }
    )
    second = SeedBundle(
        config=config,
        problems=(problem(209),),
        templates=(
            SeedTemplate(
                code="C",
                name="改名了",
                language="python",
                content="while new",
                pitfalls="别忘了",
                trigger_signal="求最短",
            ),
        ),
        plan=SeedPlan(
            name="滑动窗口计划",
            start_date=date(2026, 9, 1),
            days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
        ),
    )
    import_bundle(session, second)

    tpl = session.exec(select(Template)).one()
    assert tpl.name == "改名了"
    assert tpl.content == "while new"


def test_template_updated_at_bumps_when_content_changes(session):
    first = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    import_bundle(session, first)
    original_updated_at = session.exec(select(Template)).one().updated_at

    config = parse_topic_config(
        {
            "code": "sliding-window",
            "name": "滑动窗口",
            "time_limits": {"easy": 480, "medium": 1200, "hard": 2100},
            "card_fields": [],
        }
    )
    second = SeedBundle(
        config=config,
        problems=(problem(209),),
        templates=(
            SeedTemplate(
                code="C",
                name="不定长·求最短",
                language="python",
                content="while new content",
                pitfalls="",
                trigger_signal="",
            ),
        ),
        plan=SeedPlan(
            name="滑动窗口计划",
            start_date=date(2026, 9, 1),
            days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
        ),
    )
    import_bundle(session, second)

    tpl = session.exec(select(Template)).one()
    assert tpl.content == "while new content"
    assert tpl.updated_at > original_updated_at


def test_template_updated_at_does_not_bump_on_unchanged_reimport(session):
    bundle = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209,)),),
    )
    import_bundle(session, bundle)
    original_updated_at = session.exec(select(Template)).one().updated_at

    # Re-import the exact same bundle unchanged.
    import_bundle(session, bundle)

    tpl = session.exec(select(Template)).one()
    assert tpl.updated_at == original_updated_at


def test_import_is_atomic_on_error(session):
    """If a mid-import error occurs (e.g. a bad problem/plan reference the
    importer trusts but turns out inconsistent), nothing should be committed."""
    bundle = make_bundle(
        problems=(problem(209),),
        days=(SeedPlanDay(day_index=1, phase="", theme="", problem_lc_ids=(209, 999)),),
    )
    with pytest.raises(KeyError):
        import_bundle(session, bundle)

    session.rollback()
    assert session.exec(select(Topic)).all() == []
    assert session.exec(select(Problem)).all() == []
    assert session.exec(select(Plan)).all() == []
