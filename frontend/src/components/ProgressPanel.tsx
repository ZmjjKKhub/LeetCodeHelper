import { Fragment } from "react";

import type { ProgressOut, ProgressProblemOut } from "../api/types";
import { BUCKET_CELL_CLASSES, outcomeBucket } from "../lib/labels";

function cellClass(problem: ProgressProblemOut): string {
  if (problem.state === "done") {
    // An unmapped (older-data) outcome still counts as done -- render it as
    // "unsolved" red rather than silently dropping the cell's colour.
    const bucket = outcomeBucket(problem.outcome) ?? "unsolved";
    return BUCKET_CELL_CLASSES[bucket];
  }
  if (problem.state === "today") {
    return "bg-cell-empty shadow-[inset_0_0_0_1px_var(--today-ring)]";
  }
  return "bg-cell-empty";
}

export function ProgressPanel({ progress }: { progress: ProgressOut }) {
  const { stats } = progress;
  const firstTryAcPercent = Math.round(stats.first_try_ac_rate * 100);

  return (
    <div className="flex flex-col gap-[14px] rounded-[6px] border border-border bg-panel px-[20px] py-[18px]">
      <div className="flex items-baseline justify-between">
        <span className="text-[12px] text-muted">专题进度 · 每格一题</span>
        {progress.plan && (
          <span className="font-mono text-[12px] text-muted">
            第 {progress.plan.day_index} 天 / 共 {progress.plan.total_days} 天
          </span>
        )}
      </div>

      <div className="flex items-start gap-[14px]">
        {progress.sections.map((section, index) => (
          <Fragment key={section.section}>
            {index > 0 && <div className="h-[44px] w-px self-center bg-border" />}
            <div className="flex flex-col gap-[6px]">
              <div className="flex gap-[4px]">
                {section.problems.map((problem) => (
                  <div
                    key={problem.lc_id}
                    title={`#${problem.lc_id}`}
                    className={`h-[26px] w-[30px] rounded-[3px] ${cellClass(problem)}`}
                  />
                ))}
              </div>
              <span className="font-mono text-[10px] tracking-wide text-dim">
                {section.section} {section.section_name} · {section.done}/{section.total}
              </span>
            </div>
          </Fragment>
        ))}

        <div className="grow" />

        <div className="flex gap-[28px]">
          <div data-testid="stat-done" className="flex flex-col gap-[2px]">
            <span className="font-mono text-[22px] font-medium">
              {stats.attempted}
              <span className="text-[13px] text-dim">/{stats.total}</span>
            </span>
            <span className="text-[11px] text-muted">已做</span>
          </div>
          <div data-testid="stat-unsolved" className="flex flex-col gap-[2px]">
            <span className="font-mono text-[22px] font-medium text-alert">{stats.unsolved}</span>
            <span className="text-[11px] text-muted">没做出来</span>
          </div>
          <div data-testid="stat-first-ac" className="flex flex-col gap-[2px]">
            <span className="font-mono text-[22px] font-medium">
              {firstTryAcPercent}
              <span className="text-[13px] text-dim">%</span>
            </span>
            <span className="text-[11px] text-muted">一次 AC</span>
          </div>
        </div>
      </div>
    </div>
  );
}
