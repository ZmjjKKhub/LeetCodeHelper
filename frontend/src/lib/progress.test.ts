import { describe, expect, it } from "vitest";

import { makeHistory, makeProblem, makeToday } from "../test/fixtures";
import { buildProgress } from "./progress";

describe("buildProgress", () => {
  it("unions history (done) and today's items (done or scheduled-today) per section", () => {
    const history = makeHistory({
      rows: [
        { date: "2026-08-30", problem: makeProblem({ id: 1, lc_id: 1 }), duration_bucket: "unsolved", mark: "C", submit_count: 1, used_template: "A", first_try_ac: false },
        { date: "2026-08-31", problem: makeProblem({ id: 2, lc_id: 2 }), duration_bucket: "within", mark: "A", submit_count: 1, used_template: "A", first_try_ac: true },
      ],
    });
    const today = makeToday({
      is_fallback: false,
      items: [
        { problem: makeProblem({ id: 3, lc_id: 3 }), time_limit_sec: 1200, is_done: false, derived_template: "A", attempt: null },
        {
          problem: makeProblem({ id: 4, lc_id: 4, section: "§1.2", section_name: "进阶" }),
          time_limit_sec: 1200,
          is_done: true,
          derived_template: "A",
          attempt: { outcome: "over", submit_count: 3, used_template: "A" },
        },
      ],
    });

    const summary = buildProgress(today, history);

    expect(summary.totalCount).toBe(4);
    expect(summary.doneCount).toBe(3);
    expect(summary.unsolvedCount).toBe(1);
    // first-try AC: only problem 2 (history, first_try_ac true); problem 1
    // unsolved, problem 4 done with submit_count 3 (not first try).
    expect(summary.firstTryAcPercent).toBe(Math.round((1 / 3) * 100));

    const section1 = summary.sections.find((s) => s.section === "§1.1")!;
    expect(section1.doneCount).toBe(2);
    expect(section1.cells).toHaveLength(3);
    expect(section1.cells.map((c) => c.state)).toEqual(["unsolved", "within", "today"]);

    const section2 = summary.sections.find((s) => s.section === "§1.2")!;
    expect(section2.doneCount).toBe(1);
    expect(section2.cells[0].state).toBe("over");
  });

  it("marks a not-yet-done fallback item as 'pending' (未做), not 'today' (今天排到)", () => {
    const today = makeToday({
      is_fallback: true,
      items: [{ problem: makeProblem({ id: 1, lc_id: 1 }), time_limit_sec: 1200, is_done: false, derived_template: "A", attempt: null }],
    });

    const summary = buildProgress(today, makeHistory());

    expect(summary.sections[0].cells[0].state).toBe("pending");
    expect(summary.doneCount).toBe(0);
  });
});
