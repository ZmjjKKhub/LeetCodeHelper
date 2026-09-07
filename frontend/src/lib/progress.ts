import type { HistoryOut, TodayOut } from "../api/types";
import { outcomeBucket } from "./labels";

// The progress panel (design/Main.dc.html) shows one cell per problem in
// the *entire* topic, grouped by section, coloured by outcome. Neither
// /api/today (items are just today's scheduled 2-3 rows, or -- in fallback
// mode -- every not-yet-attempted-before-today problem) nor /api/history
// (only ever-attempted problems) alone carries the topic's full static
// catalogue, and this task's hard constraint forbids adding a new endpoint
// to expose it. This module builds the best approximation available from
// the two endpoints that do exist:
//   - every problem that has ever been attempted (from /api/history, which
//     the server already caps at HISTORY_LIMIT=500 -- see
//     leetcode_helper/web/routes/history.py)
//   - every problem in today's view (from /api/today; done or not)
// Their union is exact in fallback mode (is_fallback=True): the fallback
// query is defined as "every problem not attempted before today", so
// attempted-before (in history) + today's fallback items (everything else)
// covers the whole catalogue exactly once. It undercounts while an active
// plan is running and hasn't yet reached every problem: a problem neither
// attempted yet nor scheduled for today is simply invisible to the
// frontend and will not appear as a cell. See the task report for this
// noted as a design/API gap rather than a bug.
export type ProgressCellState = "within" | "over" | "unsolved" | "today" | "pending";

export interface ProgressCell {
  problemId: number;
  lcId: number;
  state: ProgressCellState;
}

export interface ProgressSection {
  section: string;
  sectionName: string;
  cells: ProgressCell[];
  doneCount: number;
}

export interface ProgressSummary {
  sections: ProgressSection[];
  doneCount: number;
  totalCount: number;
  unsolvedCount: number;
  firstTryAcPercent: number;
}

interface Entry {
  section: string;
  sectionName: string;
  problemId: number;
  lcId: number;
  state: ProgressCellState;
  firstTryAc: boolean | null;
}

export function buildProgress(today: TodayOut, history: HistoryOut): ProgressSummary {
  const byId = new Map<number, Entry>();

  for (const row of history.rows) {
    byId.set(row.problem.id, {
      section: row.problem.section,
      sectionName: row.problem.section_name,
      problemId: row.problem.id,
      lcId: row.problem.lc_id,
      state: row.duration_bucket,
      firstTryAc: row.first_try_ac,
    });
  }

  for (const item of today.items) {
    if (item.is_done && item.attempt) {
      const bucket = outcomeBucket(item.attempt.outcome);
      byId.set(item.problem.id, {
        section: item.problem.section,
        sectionName: item.problem.section_name,
        problemId: item.problem.id,
        lcId: item.problem.lc_id,
        // An unmapped (older-data) outcome still counts as done -- render
        // it as "unsolved" red rather than silently dropping the cell.
        state: bucket ?? "unsolved",
        firstTryAc: bucket !== null ? item.attempt.submit_count === 1 && bucket !== "unsolved" : null,
      });
    } else {
      // Only an active plan actually "schedules" a problem for today (the
      // ring in the design's legend, 今天排到); in fallback mode there is
      // no plan, so a not-yet-done item is just an ordinary not-yet-done
      // problem (未做), not "scheduled".
      byId.set(item.problem.id, {
        section: item.problem.section,
        sectionName: item.problem.section_name,
        problemId: item.problem.id,
        lcId: item.problem.lc_id,
        state: today.is_fallback ? "pending" : "today",
        firstTryAc: null,
      });
    }
  }

  const sectionMap = new Map<string, ProgressSection>();
  let doneCount = 0;
  let unsolvedCount = 0;
  let firstTryAcCount = 0;

  for (const entry of byId.values()) {
    let section = sectionMap.get(entry.section);
    if (!section) {
      section = { section: entry.section, sectionName: entry.sectionName, cells: [], doneCount: 0 };
      sectionMap.set(entry.section, section);
    }
    section.cells.push({ problemId: entry.problemId, lcId: entry.lcId, state: entry.state });

    const isDone = entry.state !== "today" && entry.state !== "pending";
    if (isDone) {
      section.doneCount += 1;
      doneCount += 1;
      if (entry.state === "unsolved") unsolvedCount += 1;
      if (entry.firstTryAc) firstTryAcCount += 1;
    }
  }

  const sections = [...sectionMap.values()]
    .sort((a, b) => a.section.localeCompare(b.section))
    .map((section) => ({
      ...section,
      cells: [...section.cells].sort((a, b) => a.lcId - b.lcId),
    }));

  return {
    sections,
    doneCount,
    totalCount: byId.size,
    unsolvedCount,
    firstTryAcPercent: doneCount > 0 ? Math.round((firstTryAcCount / doneCount) * 100) : 0,
  };
}
