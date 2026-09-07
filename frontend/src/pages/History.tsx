import { useQuery } from "@tanstack/react-query";

import { ApiError, fetchHistory, fetchMeta } from "../api/client";
import type { DurationBucketValue, HistoryRowOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { BUCKET_LABELS, DIFFICULTY_BAR_CLASSES, DIFFICULTY_LABELS, outcomeFromPair } from "../lib/labels";

const GRID_COLS = "grid-cols-[64px_1fr_96px_180px_72px_72px_72px]";

function groupByDate(rows: HistoryRowOut[]): [string, HistoryRowOut[]][] {
  const byDate = new Map<string, HistoryRowOut[]>();
  for (const row of rows) {
    const list = byDate.get(row.date) ?? [];
    list.push(row);
    byDate.set(row.date, list);
  }
  // rows arrive newest-date-first from the API (see list_history's
  // order_by); Map preserves first-seen insertion order, which is already
  // that same newest-first order -- no re-sort needed.
  return [...byDate.entries()];
}

function summarizeDay(rows: HistoryRowOut[]): string {
  const counts: Record<DurationBucketValue, number> = { within: 0, over: 0, unsolved: 0 };
  for (const row of rows) counts[row.duration_bucket] += 1;
  const nonZero = (Object.entries(counts) as [DurationBucketValue, number][]).filter(([, c]) => c > 0);
  if (nonZero.length === 1) {
    const [bucket] = nonZero[0];
    return `${rows.length} 题全部${BUCKET_LABELS[bucket]}`;
  }
  return nonZero.map(([bucket, count]) => `${count} 道${BUCKET_LABELS[bucket]}`).join(" · ");
}

function StatTile({ value, unit, label, alert }: { value: string | number; unit?: string; label: string; alert?: boolean }) {
  return (
    <div className="flex flex-col gap-[4px] rounded-[6px] border border-border bg-panel px-[16px] py-[14px]">
      <span className={`font-mono text-[24px] font-medium ${alert ? "text-alert" : "text-text"}`}>
        {value}
        {unit && <span className="text-[13px] text-dim">{unit}</span>}
      </span>
      <span className="text-[11px] text-muted">{label}</span>
    </div>
  );
}

export function HistoryPage() {
  const metaQuery = useQuery({ queryKey: ["meta"], queryFn: fetchMeta, retry: false });
  const historyQuery = useQuery({ queryKey: ["history"], queryFn: () => fetchHistory(), retry: false });

  if (metaQuery.isPending || historyQuery.isPending) {
    return (
      <main className="mx-auto flex min-h-screen max-w-[1120px] flex-col gap-[20px] bg-bg px-[32px] py-[24px] text-[13px] text-text">
        <AppHeader topicName="" />
        <p className="text-text-soft">加载中……</p>
      </main>
    );
  }

  const loadError = metaQuery.error ?? historyQuery.error;
  if (loadError) {
    const isNoTopic = loadError instanceof ApiError && loadError.status === 503;
    const detail = loadError instanceof ApiError ? loadError.detail : undefined;
    const detailText = typeof detail === "string" ? detail : "还没有导入任何 topic。";
    return (
      <main className="mx-auto flex min-h-screen max-w-[1120px] flex-col gap-[20px] bg-bg px-[32px] py-[24px] text-[13px] text-text">
        <AppHeader topicName="" />
        {isNoTopic ? (
          <article className="flex flex-col gap-[8px] rounded-[6px] border border-border bg-panel p-[18px]">
            <h1 className="text-[15px] font-medium text-text-bright">还没有可用的专题</h1>
            <p className="text-[12px] text-muted">{detailText}</p>
          </article>
        ) : (
          <p className="text-alert">加载失败：{loadError instanceof Error ? loadError.message : String(loadError)}</p>
        )}
      </main>
    );
  }

  const meta = metaQuery.data!;
  const history = historyQuery.data!;
  const rows = history.rows;

  const totalRecords = rows.length;
  const firstTryAcRate = totalRecords > 0 ? Math.round((rows.filter((r) => r.first_try_ac).length / totalRecords) * 100) : 0;
  const cRatio = totalRecords > 0 ? Math.round((rows.filter((r) => r.mark === "C").length / totalRecords) * 100) : 0;
  const practiceDays = new Set(rows.map((r) => r.date)).size;

  const outcomeLabel = (bucket: DurationBucketValue, mark: string): string => {
    const outcome = outcomeFromPair(bucket, mark);
    const label = outcome ? meta.outcomes.find((o) => o.value === outcome)?.label : undefined;
    return label ?? `${mark} / ${BUCKET_LABELS[bucket]}`;
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-[1120px] flex-col gap-[20px] bg-bg px-[32px] py-[24px] text-[13px] text-text">
      <AppHeader topicName={meta.topic.name} />

      <div className="grid grid-cols-4 gap-[12px]">
        <StatTile value={totalRecords} label="总记录" />
        <StatTile value={firstTryAcRate} unit="%" label="一次 AC 率" />
        <StatTile value={cRatio} unit="%" label="C 类占比" alert />
        <StatTile value={practiceDays} label="练习天数" />
      </div>

      {rows.length === 0 ? (
        <article className="rounded-[6px] border border-border bg-panel p-[18px]">
          <p className="text-[13px] text-text-soft">还没有任何做题记录。</p>
        </article>
      ) : (
        <div className="flex flex-col gap-[20px]">
          {history.truncated && (
            <p className="text-[12px] text-muted">
              仅显示最近 {history.limit} 条记录，更早的记录未展示。
            </p>
          )}
          {groupByDate(rows).map(([date, dayRows]) => (
            <div key={date} data-testid={`history-day-${date}`} className="flex flex-col gap-[10px]">
              <div className="flex items-baseline gap-[12px]">
                <span className="font-mono text-[14px] font-medium">{date}</span>
                <span className="ml-auto text-[11px] text-alert">{summarizeDay(dayRows)}</span>
              </div>

              <div className="overflow-hidden rounded-[6px] border border-border bg-panel">
                <div
                  className={`grid ${GRID_COLS} gap-0 border-b border-border px-[16px] py-[10px] text-[11px] tracking-wide text-dim`}
                >
                  <span>题号</span>
                  <span>题目</span>
                  <span>小节</span>
                  <span>结论</span>
                  <span className="text-center">提交</span>
                  <span className="text-center">一次 AC</span>
                  <span className="text-center">模板</span>
                </div>

                {dayRows.map((row, index) => (
                  <div
                    key={`${row.problem.id}-${row.date}`}
                    className={`grid ${GRID_COLS} items-center px-[16px] py-[13px] ${
                      index < dayRows.length - 1 ? "border-b border-border-soft" : ""
                    }`}
                  >
                    <span className="font-mono text-[12px] text-dim">{row.problem.lc_id}</span>
                    <span className="flex items-center gap-[8px]">
                      <span className={`h-[14px] w-[3px] rounded-[2px] ${DIFFICULTY_BAR_CLASSES[row.problem.difficulty]}`} />
                      {row.problem.title}
                    </span>
                    <span className="text-[12px] text-muted">{row.problem.section}</span>
                    <span className="text-[12px] text-alert">{outcomeLabel(row.duration_bucket, row.mark)}</span>
                    <span className="text-center font-mono text-[12px]">{row.submit_count}</span>
                    <span className="text-center text-[12px] text-dim">{row.first_try_ac ? "是" : "—"}</span>
                    <span className="text-center font-mono text-[12px] text-text-soft">
                      {row.used_template ?? "—"}
                    </span>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      )}

      <div className="mt-auto flex items-center gap-[20px] text-[11px] text-dim">
        {(["easy", "medium", "hard"] as const).map((difficulty) => (
          <span key={difficulty} className="flex items-center gap-[6px]">
            <span className={`h-[12px] w-[3px] rounded-[2px] ${DIFFICULTY_BAR_CLASSES[difficulty]}`} />
            {DIFFICULTY_LABELS[difficulty]}
          </span>
        ))}
        <span className="ml-auto">按天分组，一天一小结；趋势图等到有两周数据再加</span>
      </div>
    </main>
  );
}
