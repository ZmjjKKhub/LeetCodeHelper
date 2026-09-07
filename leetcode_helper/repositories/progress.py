"""进度面板的数据查询：专题的完整题目目录，而不是「今天/历史」两张局部视图的并集。

GET /api/progress 存在的理由见 leetcode_helper/api/routes/progress.py 顶部的
docstring —— /api/today 只吐今天的 2-3 题（或 fallback 模式下「所有还没做过的
题」），/api/history 只吐「做过的题」，二者的并集只在 fallback 模式下等于整个
题库；正常有计划在跑的时候，计划还没排到的题两边都看不见。这个查询直接从
Problem 表按 topic_id 取全量，就没有这个缺口。
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from itertools import groupby

from sqlmodel import Session, select

from leetcode_helper.models import (
    Attempt,
    DurationBucket,
    Plan,
    PlanDay,
    PlanItem,
    PlanStatus,
    Problem,
    Topic,
)
from leetcode_helper.services.attempts import first_try_ac
from leetcode_helper.services.topics import TopicConfig, parse_topic_config_json

# 一格的三种状态。“done” 不看结果好坏——只要这题在任何日期上有过 Attempt 就算
# done（哪怕那次是 unsolved）；“today” 是今天的 PlanDay 排到、但还没做的题；
# 其余一律 “todo”。
ProblemState = str  # "done" | "today" | "todo"


@dataclass
class ProgressProblemItem:
    problem: Problem
    state: ProblemState
    # 只在 state == "done" 时非空——见 _latest_attempt_per_problem 的选择规则。
    attempt: Attempt | None = None


@dataclass
class ProgressSectionView:
    section: str
    section_name: str
    problems: list[ProgressProblemItem]

    @property
    def total(self) -> int:
        return len(self.problems)

    @property
    def done(self) -> int:
        return sum(1 for item in self.problems if item.state == "done")


@dataclass
class ProgressPlanPosition:
    day_index: int
    total_days: int
    phase: str
    planned_date: date


@dataclass
class ProgressStats:
    total: int
    attempted: int
    unsolved: int
    first_try_ac_count: int
    # attempted 为 0 时是 0.0，不是 NaN/除零——同 first_try_ac_rate 的分母始终
    # 是 attempted（每题只按其最新一次 Attempt 计一次），不是 Attempt 行数。
    first_try_ac_rate: float


@dataclass
class ProgressView:
    config: TopicConfig
    sections: list[ProgressSectionView]
    # 今天落在某个 active 计划内时才非空——fallback 模式下没有「第几天」这回事。
    plan: ProgressPlanPosition | None
    stats: ProgressStats


def _latest_attempt_per_problem(session: Session, problem_ids: list[int]) -> dict[int, Attempt]:
    """每题最近一次 Attempt（不限日期），用于判定 done 状态和「已录入」的结果。

    一题可能被反复做过（复习、订正）；这里始终展示最新一次的结果，而不是第一
    次——同 repositories/today.py::_todays_attempts「同一天多次提交取最后一次」
    是同一个「最新的才是当前状态」的约定，只是这里跨越全部日期而不只是今天。
    升序按 (attempt_date, id) 排序后用 dict 覆盖写入，最后一次覆盖的就是最新
    的一条。
    """
    if not problem_ids:
        return {}
    rows = session.exec(
        select(Attempt)
        .where(Attempt.problem_id.in_(problem_ids))
        .order_by(Attempt.attempt_date, Attempt.id)
    ).all()
    return {attempt.problem_id: attempt for attempt in rows}


def get_progress_view(session: Session, *, topic_id: int, today: date) -> ProgressView:
    topic = session.get(Topic, topic_id)
    if topic is None:
        raise LookupError(f"topic_id={topic_id} 不存在")
    config = parse_topic_config_json(topic.config_json)

    # 与 repositories/today.py::get_today_view 完全相同的「今天属于哪个计划」
    # 查询（同样的 active-only、同一天多计划撞车时按 Plan.id/PlanDay.id 取最小
    # 的确定性规则）——这里只是多用它来算 day_index/total_days，而不是取当天的
    # 题目列表。
    day = session.exec(
        select(PlanDay)
        .join(Plan, Plan.id == PlanDay.plan_id)
        .where(
            Plan.topic_id == topic_id,
            Plan.status == PlanStatus.active,
            PlanDay.planned_date == today,
        )
        .order_by(Plan.id, PlanDay.id)
    ).first()

    plan_position: ProgressPlanPosition | None = None
    today_problem_ids: set[int] = set()
    if day is not None:
        total_days = len(
            session.exec(select(PlanDay.id).where(PlanDay.plan_id == day.plan_id)).all()
        )
        plan_position = ProgressPlanPosition(
            day_index=day.day_index,
            total_days=total_days,
            phase=day.phase,
            planned_date=day.planned_date,
        )
        today_problem_ids = set(
            session.exec(
                select(PlanItem.problem_id).where(PlanItem.plan_day_id == day.id)
            ).all()
        )

    problems = session.exec(
        select(Problem).where(Problem.topic_id == topic_id).order_by(Problem.section, Problem.lc_id)
    ).all()
    latest_attempts = _latest_attempt_per_problem(session, [p.id for p in problems])

    sections: list[ProgressSectionView] = []
    attempted = 0
    unsolved = 0
    first_try_ac_count = 0

    for section, group in groupby(problems, key=lambda p: p.section):
        group_list = list(group)
        items: list[ProgressProblemItem] = []
        for problem in group_list:
            attempt = latest_attempts.get(problem.id)
            if attempt is not None:
                state: ProblemState = "done"
                attempted += 1
                if attempt.duration_bucket is DurationBucket.unsolved:
                    unsolved += 1
                if first_try_ac(attempt):
                    first_try_ac_count += 1
            elif problem.id in today_problem_ids:
                state = "today"
            else:
                state = "todo"
            items.append(ProgressProblemItem(problem=problem, state=state, attempt=attempt))
        sections.append(
            ProgressSectionView(
                section=section, section_name=group_list[0].section_name, problems=items
            )
        )

    stats = ProgressStats(
        total=len(problems),
        attempted=attempted,
        unsolved=unsolved,
        first_try_ac_count=first_try_ac_count,
        first_try_ac_rate=(first_try_ac_count / attempted) if attempted else 0.0,
    )

    return ProgressView(config=config, sections=sections, plan=plan_position, stats=stats)
