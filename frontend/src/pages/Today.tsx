import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";

import { ApiError, fetchMeta, fetchProgress, fetchToday, postAttempt } from "../api/client";
import type { AttemptCreateIn, TodayItemOut, TodayOut } from "../api/types";
import { AppHeader } from "../components/AppHeader";
import { ProblemRow } from "../components/ProblemRow";
import { ProgressPanel } from "../components/ProgressPanel";
import { BUCKET_LABELS } from "../lib/labels";

function Shell({ topicName, children }: { topicName?: string; children: ReactNode }) {
  return (
    <main className="mx-auto flex min-h-screen max-w-[1120px] flex-col gap-[20px] bg-bg px-[32px] py-[24px] text-[13px] text-text">
      <AppHeader topicName={topicName ?? ""} />
      {children}
    </main>
  );
}

function groupBySection(items: TodayItemOut[]): [string, TodayItemOut[]][] {
  const bySection = new Map<string, TodayItemOut[]>();
  for (const item of [...items].sort((a, b) => a.problem.lc_id - b.problem.lc_id)) {
    const list = bySection.get(item.problem.section) ?? [];
    list.push(item);
    bySection.set(item.problem.section, list);
  }
  return [...bySection.entries()].sort(([a], [b]) => a.localeCompare(b));
}

const SEED_COMMAND = "uv run python -m leetcode_helper.seed data/topics/sliding-window";

function DateLine({ today }: { today: TodayOut }) {
  return (
    <div className="flex items-baseline gap-[12px]">
      <span className="font-mono text-[15px] font-medium">{today.date}</span>
      {today.is_fallback ? (
        <span className="text-[12px] text-text-soft">
          今天没有排期，下面是本专题所有还没做过的题，随便挑一道。
        </span>
      ) : (
        <>
          <span className="text-[12px] text-muted">{today.phase}</span>
          {today.theme && (
            <>
              <span className="text-[12px] text-dim">·</span>
              <span className="text-[12px] text-text-soft">{today.theme}</span>
            </>
          )}
        </>
      )}
    </div>
  );
}

function EmptyDayNotice({ isFallback }: { isFallback: boolean }) {
  return (
    <article className="flex flex-col gap-[8px] rounded-[6px] border border-border bg-panel p-[18px]">
      <p className="text-[13px] text-text-soft">没有待做的题了。</p>
      {isFallback ? (
        <>
          <p className="text-[12px] text-muted">
            本专题所有题都练完了。想继续练，先往 data/topics/sliding-window 里加新题，再重新导入一遍：
          </p>
          <pre className="overflow-x-auto rounded-[4px] bg-subpanel px-[12px] py-[9px] font-mono text-[12px] text-text-soft">
            {SEED_COMMAND}
          </pre>
        </>
      ) : (
        <p className="text-[12px] text-muted">今天的排期没有安排题目。</p>
      )}
    </article>
  );
}

function Legend() {
  const items: [string, string][] = [
    ["bg-easy", BUCKET_LABELS.within],
    ["bg-medium", BUCKET_LABELS.over],
    ["bg-hard", BUCKET_LABELS.unsolved],
    ["bg-cell-empty", "未做"],
    ["bg-cell-empty shadow-[inset_0_0_0_1px_var(--today-ring)]", "今天排到"],
  ];
  return (
    <div className="mt-auto flex items-center gap-[20px] text-[11px] text-dim">
      {items.map(([cls, label]) => (
        <span key={label} className="flex items-center gap-[6px]">
          <span className={`h-[10px] w-[10px] rounded-[2px] ${cls}`} />
          {label}
        </span>
      ))}
      <span className="ml-auto">难度用左侧色条与标签：简单 / 中等 / 困难</span>
    </div>
  );
}

export function TodayPage() {
  const queryClient = useQueryClient();
  const metaQuery = useQuery({ queryKey: ["meta"], queryFn: fetchMeta, retry: false });
  const todayQuery = useQuery({ queryKey: ["today"], queryFn: () => fetchToday(), retry: false });
  const progressQuery = useQuery({
    queryKey: ["progress"],
    queryFn: () => fetchProgress(),
    retry: false,
  });

  const [openId, setOpenId] = useState<number | null>(null);

  const mutation = useMutation({
    mutationFn: postAttempt,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["today"] });
      queryClient.invalidateQueries({ queryKey: ["history"] });
      queryClient.invalidateQueries({ queryKey: ["progress"] });
      setOpenId(null);
    },
  });

  if (metaQuery.isPending || todayQuery.isPending) {
    return (
      <Shell>
        <p className="text-text-soft">加载中……</p>
      </Shell>
    );
  }

  const loadError = metaQuery.error ?? todayQuery.error;
  if (loadError) {
    if (loadError instanceof ApiError && loadError.status === 503) {
      return (
        <Shell>
          <article className="flex flex-col gap-[8px] rounded-[6px] border border-border bg-panel p-[18px]">
            <h1 className="text-[15px] font-medium text-text-bright">还没有可用的专题</h1>
            <p className="text-[12px] text-muted">
              {typeof loadError.detail === "string" ? loadError.detail : "还没有导入任何 topic。"}
            </p>
          </article>
        </Shell>
      );
    }
    return (
      <Shell>
        <p className="text-alert">
          加载失败：{loadError instanceof Error ? loadError.message : String(loadError)}
        </p>
      </Shell>
    );
  }

  const meta = metaQuery.data!;
  const today = todayQuery.data!;
  const progress = progressQuery.data;

  const activeProblemId = mutation.variables?.problem_id ?? null;
  const submitErrorMessage =
    mutation.isError && activeProblemId != null
      ? mutation.error instanceof ApiError && typeof mutation.error.detail === "string"
        ? mutation.error.detail
        : mutation.error instanceof Error
          ? mutation.error.message
          : "请求失败，请重试"
      : null;

  function handleSubmit(payload: AttemptCreateIn) {
    mutation.mutate(payload);
  }

  function renderRow(item: TodayItemOut) {
    return (
      <ProblemRow
        key={item.problem.id}
        item={item}
        meta={meta}
        open={openId === item.problem.id}
        onToggle={() => setOpenId((id) => (id === item.problem.id ? null : item.problem.id))}
        onSubmit={handleSubmit}
        isSubmitting={mutation.isPending && activeProblemId === item.problem.id}
        errorMessage={activeProblemId === item.problem.id ? submitErrorMessage : null}
      />
    );
  }

  return (
    <Shell topicName={meta.topic.name}>
      {progress && <ProgressPanel progress={progress} />}

      <DateLine today={today} />

      {today.items.length === 0 ? (
        <EmptyDayNotice isFallback={today.is_fallback} />
      ) : today.is_fallback ? (
        <div className="flex flex-col gap-[18px]">
          {groupBySection(today.items).map(([section, items]) => (
            <div key={section} className="flex flex-col gap-[10px]">
              <h3 className="text-[13px] font-medium text-text">
                {section} <span className="text-muted">{items[0].problem.section_name}</span>
              </h3>
              {items.map(renderRow)}
            </div>
          ))}
        </div>
      ) : (
        <div className="flex flex-col gap-[10px]">{today.items.map(renderRow)}</div>
      )}

      <Legend />
    </Shell>
  );
}
