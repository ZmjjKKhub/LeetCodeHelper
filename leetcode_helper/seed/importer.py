"""把校验过的 SeedBundle 写库。按自然键 upsert，支持增量导入。

约定（规格 §9.3 之上的补充，plan 文档没写清楚的部分）：

- Upsert 只覆盖“种子拥有”的字段：Topic.name/config_json、Problem 的题面信息、
  Template 的正文、PlanDay.phase/theme、PlanItem.sort_order。
- 绝不覆盖“用户拥有”的字段：Plan.status、PlanDay.status/actual_date、
  PlanItem.status。这些字段一旦被用户改过，就不再由种子数据驱动。
- planned_date 只在 PlanDay 首次创建时从 start_date 派生；后续重新导入
  同一个 plan（哪怕 start_date 没变）也不会覆盖已存在的 planned_date——
  未来阶段允许用户整体顺延排期，那个改动直接写 planned_date，这里不能把它冲掉。
- 从 problems: 列表里去掉的题目 / 从 days: 里去掉的整天，对应的 PlanItem /
  PlanDay 只有在“用户还没碰过”（status 仍是 pending，且 PlanDay 没有
  actual_date）时才会被物理删除；一旦用户记录过真实进度，这些行就保留在库里，
  不再被本次导入触碰，避免悄悄丢失已完成的记录。
- 整个函数只在最后 commit 一次：中途任何一步失败（比如 KeyError），
  之前 flush 过的改动都不会落盘，调用方对同一个 session rollback 后即可复用。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import timedelta

from sqlmodel import Session, select

from leetcode_helper.models import (
    DayStatus,
    ItemStatus,
    Plan,
    PlanDay,
    PlanItem,
    PlanStatus,
    Problem,
    Template,
    Topic,
)
from leetcode_helper.seed.bundle import SeedBundle


@dataclass
class ImportReport:
    problems_created: int = 0
    problems_updated: int = 0
    templates_created: int = 0
    templates_updated: int = 0
    plan_days_created: int = 0
    plan_days_updated: int = 0
    plan_days_removed: int = 0
    plan_items_created: int = 0
    plan_items_updated: int = 0
    plan_items_removed: int = 0

    def summary(self) -> str:
        parts = [
            f"题目 +{self.problems_created} / 更新 {self.problems_updated}",
            f"模板 +{self.templates_created} / 更新 {self.templates_updated}",
        ]
        days_part = f"排期天数 +{self.plan_days_created} / 更新 {self.plan_days_updated}"
        if self.plan_days_removed:
            days_part += f" / 删除 {self.plan_days_removed}"
        parts.append(days_part)

        items_part = f"排期任务 +{self.plan_items_created} / 更新 {self.plan_items_updated}"
        if self.plan_items_removed:
            items_part += f" / 删除 {self.plan_items_removed}"
        parts.append(items_part)
        return "，".join(parts)


def import_bundle(session: Session, bundle: SeedBundle) -> ImportReport:
    report = ImportReport()
    config = bundle.config

    # --- Topic：按 code upsert，name/config_json 是种子拥有的字段 ---
    topic = session.exec(select(Topic).where(Topic.code == config.code)).first()
    if topic is None:
        topic = Topic(code=config.code, name=config.name, config_json=config.to_json())
        session.add(topic)
    else:
        topic.name = config.name
        topic.config_json = config.to_json()
    session.flush()

    # --- Template：按 (topic_id, code) upsert ---
    for seed_template in bundle.templates:
        existing = session.exec(
            select(Template).where(
                Template.topic_id == topic.id, Template.code == seed_template.code
            )
        ).first()
        if existing is None:
            session.add(
                Template(
                    topic_id=topic.id,
                    code=seed_template.code,
                    name=seed_template.name,
                    language=seed_template.language,
                    content=seed_template.content,
                    pitfalls=seed_template.pitfalls,
                    trigger_signal=seed_template.trigger_signal,
                )
            )
            report.templates_created += 1
        else:
            existing.name = seed_template.name
            existing.language = seed_template.language
            existing.content = seed_template.content
            existing.pitfalls = seed_template.pitfalls
            existing.trigger_signal = seed_template.trigger_signal
            report.templates_updated += 1
    session.flush()

    # --- Problem：按 (topic_id, lc_id) upsert ---
    problem_rows: list[tuple[int, Problem]] = []
    for seed_problem in bundle.problems:
        existing = session.exec(
            select(Problem).where(
                Problem.topic_id == topic.id, Problem.lc_id == seed_problem.lc_id
            )
        ).first()
        if existing is None:
            existing = Problem(topic_id=topic.id, lc_id=seed_problem.lc_id)
            session.add(existing)
            report.problems_created += 1
        else:
            report.problems_updated += 1
        existing.title = seed_problem.title
        existing.url = seed_problem.url
        existing.difficulty = seed_problem.difficulty
        existing.section = seed_problem.section
        existing.section_name = seed_problem.section_name
        existing.is_starred = seed_problem.is_starred
        existing.is_premium = seed_problem.is_premium
        existing.is_optional = seed_problem.is_optional
        existing.default_template = seed_problem.default_template
        problem_rows.append((seed_problem.lc_id, existing))
    session.flush()
    problem_ids: dict[int, int] = {lc_id: row.id for lc_id, row in problem_rows}

    # --- Plan：按 (topic_id, name) upsert。status 是用户拥有的字段，只在创建时设默认值 ---
    plan = session.exec(
        select(Plan).where(Plan.topic_id == topic.id, Plan.name == bundle.plan.name)
    ).first()
    if plan is None:
        plan = Plan(
            topic_id=topic.id,
            name=bundle.plan.name,
            start_date=bundle.plan.start_date,
            status=PlanStatus.active,
        )
        session.add(plan)
    else:
        plan.start_date = bundle.plan.start_date
    session.flush()

    seed_day_indexes = {d.day_index for d in bundle.plan.days}
    existing_days = session.exec(select(PlanDay).where(PlanDay.plan_id == plan.id)).all()
    existing_days_by_index = {d.day_index: d for d in existing_days}

    # 删除已从 plan_default.yaml 的 days 中移除、且用户完全没碰过的整天
    # （连同它底下同样没碰过的 PlanItem）。碰过的天（status != pending 或
    # 有 actual_date）一律保留，不做任何改动。
    for day_index, day in existing_days_by_index.items():
        if day_index in seed_day_indexes:
            continue
        if day.status != DayStatus.pending or day.actual_date is not None:
            continue
        day_items = session.exec(
            select(PlanItem).where(PlanItem.plan_day_id == day.id)
        ).all()
        if any(item.status != ItemStatus.pending for item in day_items):
            continue
        for item in day_items:
            session.delete(item)
        session.delete(day)
        report.plan_days_removed += 1
        report.plan_items_removed += len(day_items)
    session.flush()

    for seed_day in bundle.plan.days:
        # existing_days_by_index only ever loses entries the removal loop above
        # deleted, and it only deletes indexes NOT in seed_day_indexes — so any
        # index we look up here that was present before is still a live row.
        day = existing_days_by_index.get(seed_day.day_index)
        if day is None:
            day = PlanDay(
                plan_id=plan.id,
                day_index=seed_day.day_index,
                planned_date=plan.start_date + timedelta(days=seed_day.day_index - 1),
            )
            session.add(day)
            report.plan_days_created += 1
        else:
            report.plan_days_updated += 1
        # planned_date 只在创建时派生，见函数顶部说明，这里不再改写。
        day.phase = seed_day.phase
        day.theme = seed_day.theme
        session.flush()

        existing_items = session.exec(
            select(PlanItem).where(PlanItem.plan_day_id == day.id)
        ).all()
        existing_items_by_problem = {item.problem_id: item for item in existing_items}
        seed_problem_ids = {problem_ids[lc_id] for lc_id in seed_day.problem_lc_ids}

        # 从当天 problems 列表移除、且用户没碰过的 PlanItem 直接删除；
        # 已经 done/deferred 的保留，不再纳入本次导入的排序范围。
        for problem_id, item in list(existing_items_by_problem.items()):
            if problem_id in seed_problem_ids:
                continue
            if item.status == ItemStatus.pending:
                session.delete(item)
                del existing_items_by_problem[problem_id]
                report.plan_items_removed += 1

        for sort_order, lc_id in enumerate(seed_day.problem_lc_ids):
            problem_id = problem_ids[lc_id]
            item = existing_items_by_problem.get(problem_id)
            if item is None:
                item = PlanItem(
                    plan_day_id=day.id, problem_id=problem_id, status=ItemStatus.pending
                )
                session.add(item)
                report.plan_items_created += 1
            else:
                report.plan_items_updated += 1
            item.sort_order = sort_order
        session.flush()

    session.commit()
    return report
