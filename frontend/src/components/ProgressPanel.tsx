import { Fragment } from "react";

import type { ProgressSummary } from "../lib/progress";

const CELL_CLASS: Record<string, string> = {
  within: "bg-easy",
  over: "bg-medium",
  unsolved: "bg-hard",
  today: "bg-cell-empty shadow-[inset_0_0_0_1px_var(--today-ring)]",
  pending: "bg-cell-empty",
};

export function ProgressPanel({ summary }: { summary: ProgressSummary }) {
  return (
    <div className="flex flex-col gap-[14px] rounded-[6px] border border-border bg-panel px-[20px] py-[18px]">
      <div className="flex items-baseline justify-between">
        <span className="text-[12px] text-muted">专题进度 · 每格一题</span>
      </div>

      <div className="flex items-start gap-[14px]">
        {summary.sections.map((section, index) => (
          <Fragment key={section.section}>
            {index > 0 && <div className="h-[44px] w-px self-center bg-border" />}
            <div className="flex flex-col gap-[6px]">
              <div className="flex gap-[4px]">
                {section.cells.map((cell) => (
                  <div
                    key={cell.problemId}
                    title={`#${cell.lcId}`}
                    className={`h-[26px] w-[30px] rounded-[3px] ${CELL_CLASS[cell.state]}`}
                  />
                ))}
              </div>
              <span className="font-mono text-[10px] tracking-wide text-dim">
                {section.section} {section.sectionName} · {section.doneCount}/{section.cells.length}
              </span>
            </div>
          </Fragment>
        ))}

        <div className="grow" />

        <div className="flex gap-[28px]">
          <div data-testid="stat-done" className="flex flex-col gap-[2px]">
            <span className="font-mono text-[22px] font-medium">
              {summary.doneCount}
              <span className="text-[13px] text-dim">/{summary.totalCount}</span>
            </span>
            <span className="text-[11px] text-muted">已做</span>
          </div>
          <div data-testid="stat-unsolved" className="flex flex-col gap-[2px]">
            <span className="font-mono text-[22px] font-medium text-alert">{summary.unsolvedCount}</span>
            <span className="text-[11px] text-muted">没做出来</span>
          </div>
          <div data-testid="stat-first-ac" className="flex flex-col gap-[2px]">
            <span className="font-mono text-[22px] font-medium">
              {summary.firstTryAcPercent}
              <span className="text-[13px] text-dim">%</span>
            </span>
            <span className="text-[11px] text-muted">一次 AC</span>
          </div>
        </div>
      </div>
    </div>
  );
}
