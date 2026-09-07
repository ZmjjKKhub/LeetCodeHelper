import type {
  HistoryOut,
  MetaOut,
  ProblemOut,
  ProgressOut,
  ProgressSectionOut,
  TodayItemOut,
  TodayOut,
} from "../api/types";

export const META: MetaOut = {
  topic: { code: "sliding-window", name: "滑动窗口" },
  templates: [
    { code: "A", name: "定长滑窗（入 → 更新 → 出）", trigger_signal: "窗口长度固定为 k，题目直接给出 k。" },
    { code: "C", name: "不定长 · 求最短（越长越合法）", trigger_signal: "题目问「最短 / 最小」。" },
  ],
  outcomes: [
    { value: "within_solid", label: "限时内做出来，思路清楚", consequence: "不排复习" },
    { value: "within_shaky", label: "限时内，但靠硬套模板/蒙的", consequence: "复习 2 轮（D+3、D+14）" },
    { value: "over", label: "超时才做出来", consequence: "复习 2 轮（D+3、D+14）" },
    { value: "unsolved", label: "没做出来 / 看了题解", consequence: "复习 4 轮（D+1、D+3、D+7、D+14）" },
  ],
};

export function makeProblem(overrides: Partial<ProblemOut> & { id: number; lc_id: number }): ProblemOut {
  return {
    title: `题目 ${overrides.lc_id}`,
    url: `https://leetcode.cn/problems/p${overrides.lc_id}/`,
    difficulty: "medium",
    section: "§1.1",
    section_name: "定长滑动窗口 · 基础",
    is_starred: false,
    is_optional: false,
    ...overrides,
  };
}

export function makeToday(overrides: Partial<TodayOut> & { items: TodayItemOut[] }): TodayOut {
  return {
    topic: META.topic,
    date: "2026-09-02",
    is_fallback: false,
    phase: "阶段一 · 定长滑窗",
    theme: "把模板 A 的「入-更新-出」三步写死",
    ...overrides,
  };
}

export function makeHistory(overrides: Partial<HistoryOut> = {}): HistoryOut {
  return {
    rows: [],
    limit: 500,
    truncated: false,
    ...overrides,
  };
}

export function makeProgress(overrides: Partial<ProgressOut> = {}): ProgressOut {
  return {
    topic: META.topic,
    plan: {
      day_index: 3,
      total_days: 5,
      phase: "阶段一 · 定长滑窗",
      planned_date: "2026-09-02",
    },
    sections: [],
    stats: { total: 0, attempted: 0, unsolved: 0, first_try_ac_count: 0, first_try_ac_rate: 0 },
    ...overrides,
  };
}

export function makeProgressSection(
  overrides: Partial<ProgressSectionOut> & { section: string },
): ProgressSectionOut {
  return {
    section_name: "定长滑动窗口 · 基础",
    problems: [],
    total: overrides.problems?.length ?? 0,
    done: overrides.problems?.filter((p) => p.state === "done").length ?? 0,
    ...overrides,
  };
}
