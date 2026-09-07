import { useState } from "react";

import type { AttemptCreateIn, MetaOut, TodayItemOut } from "../api/types";
import { OUTCOME_CONSEQUENCE_TEXT_CLASSES } from "../lib/labels";

interface EntryPanelProps {
  item: TodayItemOut;
  meta: MetaOut;
  onSubmit: (payload: AttemptCreateIn) => void;
  isSubmitting: boolean;
  errorMessage: string | null;
}

// The expanded entry form for one problem row. Mounted only while the row
// is open (see ProblemRow) -- that means every open recomputes its initial
// state (submit_count, used_template) fresh from `item`, which is exactly
// interaction rule #2's "reopens the panel prefilled with what was
// recorded" behaviour, with no extra effect/sync code needed.
export function EntryPanel({ item, meta, onSubmit, isSubmitting, errorMessage }: EntryPanelProps) {
  const [count, setCount] = useState(() => item.attempt?.submit_count ?? 1);
  const [templateCode, setTemplateCode] = useState(() => {
    if (item.is_done) return item.attempt?.used_template ?? "";
    return item.derived_template ?? "";
  });
  const [editTemplate, setEditTemplate] = useState(false);

  const currentOutcome = item.is_done ? item.attempt?.outcome ?? null : null;
  const currentOption = meta.templates.find((t) => t.code === templateCode) ?? null;
  // 规格 §5 R6: the template actually recorded may differ from the one the
  // section derivation expects -- both must stay visible, never just the
  // one that "won". Only meaningful once something has actually been
  // recorded (a pending row has nothing to differ from yet).
  const templateMismatch =
    item.is_done && !!item.derived_template && item.derived_template !== templateCode;

  function submit(outcome: string) {
    onSubmit({
      problem_id: item.problem.id,
      outcome,
      submit_count: count,
      used_template: templateCode || null,
    });
  }

  return (
    <div className="flex flex-col gap-[16px]">
      {errorMessage && <p className="text-[12px] text-alert">保存失败：{errorMessage}</p>}

      <div className="grid grid-cols-2 gap-x-[24px] gap-y-[12px]">
        <div className="flex items-center justify-between rounded-[4px] bg-subpanel px-[12px] py-[9px]">
          <span className="text-[12px] text-muted">模板</span>
          {editTemplate ? (
            <select
              aria-label="选择模板"
              autoFocus
              value={templateCode}
              onChange={(event) => setTemplateCode(event.target.value)}
              onBlur={() => setEditTemplate(false)}
              className="rounded border border-btn-border bg-card px-[6px] py-[2px] text-[12px] text-text"
            >
              <option value="">无</option>
              {meta.templates.map((tmpl) => (
                <option key={tmpl.code} value={tmpl.code} title={tmpl.trigger_signal}>
                  {tmpl.code} · {tmpl.name}
                </option>
              ))}
            </select>
          ) : (
            <span className="text-[12px]">
              {currentOption ? `${currentOption.code} · ${currentOption.name}` : "无"}
              {templateMismatch && (
                <span className="text-dim"> （原本预期 {item.derived_template}）</span>
              )}{" "}
              <button
                type="button"
                onClick={() => setEditTemplate(true)}
                className="ml-[4px] rounded border border-btn-border px-[6px] py-[1px] text-[11px] text-muted hover:text-text"
              >
                改
              </button>
            </span>
          )}
        </div>

        {/* 提交次数 must sit before the outcome buttons in DOM order (rule
            #4): a click on any outcome button submits immediately, so the
            stepper has to already be reachable by then. Both [-]/[+] are
            type="button" so neither can ever trigger a submit itself. */}
        <div className="flex items-center justify-between rounded-[4px] bg-subpanel px-[12px] py-[9px]">
          <span className="text-[12px] text-muted">提交次数</span>
          <div className="flex items-center gap-[12px]" role="group" aria-label="提交次数">
            <button
              type="button"
              aria-label="减少提交次数"
              onClick={() => setCount((c) => Math.max(1, c - 1))}
              className="text-muted hover:text-text"
            >
              −
            </button>
            <span className="font-mono text-[13px]">{count}</span>
            <button
              type="button"
              aria-label="增加提交次数"
              onClick={() => setCount((c) => c + 1)}
              className="text-muted hover:text-text"
            >
              +
            </button>
          </div>
        </div>
      </div>

      <div className="flex flex-col gap-[8px]">
        <span className="text-[12px] text-muted">
          今天做得怎么样？<span className="text-dim2">　点一下即保存</span>
        </span>
        <div className="grid grid-cols-2 gap-[8px]">
          {meta.outcomes.map((outcome) => {
            const isCurrent = currentOutcome === outcome.value;
            return (
              <button
                key={outcome.value}
                type="button"
                title={outcome.consequence}
                disabled={isSubmitting}
                aria-pressed={isCurrent}
                onClick={() => submit(outcome.value)}
                className={`flex flex-col gap-[3px] rounded-[5px] border px-[14px] py-[11px] text-left disabled:opacity-60 ${
                  isCurrent ? "border-sel-border bg-sel-bg" : "border-btn-border hover:border-border-strong"
                }`}
              >
                <span className={`text-[13px] ${isCurrent ? "text-text-bright" : "text-text"}`}>
                  {outcome.label}
                </span>
                <span className={`text-[11px] ${OUTCOME_CONSEQUENCE_TEXT_CLASSES[outcome.value] ?? "text-muted"}`}>
                  {outcome.consequence}
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}
