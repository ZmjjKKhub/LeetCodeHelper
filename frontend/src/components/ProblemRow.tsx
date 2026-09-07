import type { AttemptCreateIn, MetaOut, TodayItemOut } from "../api/types";
import { formatLimit } from "../lib/format";
import { DIFFICULTY_BAR_CLASSES, DIFFICULTY_LABELS, DIFFICULTY_TEXT_CLASSES } from "../lib/labels";
import { EntryPanel } from "./EntryPanel";

interface ProblemRowProps {
  item: TodayItemOut;
  meta: MetaOut;
  open: boolean;
  onToggle: () => void;
  onSubmit: (payload: AttemptCreateIn) => void;
  isSubmitting: boolean;
  errorMessage: string | null;
}

export function ProblemRow({
  item,
  meta,
  open,
  onToggle,
  onSubmit,
  isSubmitting,
  errorMessage,
}: ProblemRowProps) {
  const { problem } = item;
  const currentOutcomeLabel = item.is_done
    ? meta.outcomes.find((o) => o.value === item.attempt?.outcome)?.label
    : undefined;

  return (
    <article
      id={`problem-${problem.id}`}
      className={`flex overflow-hidden rounded-[6px] border ${
        open ? "border-border-strong bg-panel" : "border-border bg-card"
      }`}
    >
      <div className={`w-[3px] shrink-0 ${DIFFICULTY_BAR_CLASSES[problem.difficulty]}`} />
      <div className="flex grow flex-col gap-[16px] px-[18px] py-[14px]">
        <div className="flex items-center gap-[12px]">
          <a
            href={problem.url}
            target="_blank"
            rel="noopener noreferrer"
            className="font-mono text-[12px] text-dim hover:text-text"
          >
            {problem.lc_id}
          </a>
          <a
            href={problem.url}
            target="_blank"
            rel="noopener noreferrer"
            className={`grow text-[15px] ${open ? "font-medium" : "font-normal"} text-text hover:text-text-bright`}
          >
            {problem.title}
          </a>
          {item.is_done && currentOutcomeLabel && (
            <span className="text-[11px] text-muted">已录入：{currentOutcomeLabel}</span>
          )}
          <span
            className={`rounded-[3px] bg-med-chip-bg px-[8px] py-[2px] text-[11px] ${DIFFICULTY_TEXT_CLASSES[problem.difficulty]}`}
          >
            {DIFFICULTY_LABELS[problem.difficulty]}
          </span>
          <span className="text-[11px] text-muted">{problem.section}</span>
          <span className="font-mono text-[12px] text-text-soft">{formatLimit(item.time_limit_sec)}</span>
          <button
            type="button"
            onClick={onToggle}
            className="rounded border border-btn-border px-[10px] py-[3px] text-[11px] text-muted hover:text-text"
          >
            {item.is_done ? "修改" : "录入"}
          </button>
        </div>

        {open && (
          <EntryPanel item={item} meta={meta} onSubmit={onSubmit} isSubmitting={isSubmitting} errorMessage={errorMessage} />
        )}
      </div>
    </article>
  );
}
