import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { TodayItemOut, TodayOut } from "../api/types";
import { META, makeProblem, makeProgress, makeProgressSection, makeToday } from "../test/fixtures";
import { TodayPage } from "./Today";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchMeta: vi.fn(),
    fetchToday: vi.fn(),
    fetchProgress: vi.fn(),
    postAttempt: vi.fn(),
  };
});

import { fetchMeta, fetchProgress, fetchToday, postAttempt } from "../api/client";

function renderToday() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <TodayPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(fetchMeta).mockResolvedValue(META);
  vi.mocked(fetchToday).mockResolvedValue(makeToday({ items: [] }));
  vi.mocked(fetchProgress).mockResolvedValue(makeProgress());
});

afterEach(() => {
  vi.restoreAllMocks();
});

describe("TodayPage -- progress panel", () => {
  it("renders one cell per problem grouped per section, with the right per-state counts", async () => {
    // §1.1: 3 done (all "没做出来"/unsolved) + 1 todo = 4 problems, 3/4 done.
    // §1.2: 1 todo = 1 problem, 0/1 done.
    const section1 = makeProgressSection({
      section: "§1.1",
      problems: [
        { lc_id: 1001, title: "题目1001", state: "done", outcome: "unsolved" },
        { lc_id: 1002, title: "题目1002", state: "done", outcome: "unsolved" },
        { lc_id: 1003, title: "题目1003", state: "done", outcome: "unsolved" },
        { lc_id: 1004, title: "题目1004", state: "todo", outcome: null },
      ],
    });
    const section2 = makeProgressSection({
      section: "§1.2",
      section_name: "定长滑动窗口 · 进阶（选做）",
      problems: [{ lc_id: 2001, title: "题目2001", state: "todo", outcome: null }],
    });
    vi.mocked(fetchProgress).mockResolvedValue(
      makeProgress({
        sections: [section1, section2],
        stats: { total: 5, attempted: 3, unsolved: 3, first_try_ac_count: 0, first_try_ac_rate: 0 },
      }),
    );

    renderToday();

    expect(await screen.findByText(/§1\.1.*3\/4/)).toBeInTheDocument();
    expect(await screen.findByText(/§1\.2.*0\/1/)).toBeInTheDocument();
    expect(document.querySelectorAll('[title^="#"]')).toHaveLength(5);

    // 已做 3/5, 没做出来 3, 一次 AC 0%
    expect(screen.getByTestId("stat-done").textContent).toBe("3/5已做");
    expect(screen.getByTestId("stat-unsolved").textContent).toBe("3没做出来");
    expect(screen.getByTestId("stat-first-ac").textContent).toBe("0%一次 AC");
  });

  it("shows the day readout when a plan is active", async () => {
    vi.mocked(fetchProgress).mockResolvedValue(
      makeProgress({ plan: { day_index: 3, total_days: 5, phase: "阶段一", planned_date: "2026-09-02" } }),
    );

    renderToday();

    expect(await screen.findByText(/第 3 天.*共 5 天/)).toBeInTheDocument();
  });

  it("omits the day readout when today falls outside any active plan", async () => {
    vi.mocked(fetchProgress).mockResolvedValue(makeProgress({ plan: null }));

    renderToday();

    // Wait for the panel to render (via the always-present header label)
    // before asserting on the readout's absence.
    expect(await screen.findByText("专题进度 · 每格一题")).toBeInTheDocument();
    expect(screen.queryByText(/第 \d+ 天/)).not.toBeInTheDocument();
  });
});

function pendingItem(overrides: Partial<TodayItemOut> = {}): TodayItemOut {
  return {
    problem: makeProblem({ id: 501, lc_id: 501 }),
    time_limit_sec: 1200,
    is_done: false,
    derived_template: "A",
    attempt: null,
    ...overrides,
  };
}

function doneItem(overrides: Partial<TodayItemOut> = {}): TodayItemOut {
  return {
    problem: makeProblem({ id: 501, lc_id: 501 }),
    time_limit_sec: 1200,
    is_done: true,
    derived_template: "A",
    attempt: { outcome: "unsolved", submit_count: 2, used_template: "A" },
    ...overrides,
  };
}

describe("TodayPage -- recording an attempt", () => {
  it("expands the panel on click, posts once on an outcome click, and the row becomes done", async () => {
    let calls = 0;
    vi.mocked(fetchToday).mockImplementation(() => {
      const today: TodayOut = calls === 0 ? makeToday({ items: [pendingItem()] }) : makeToday({ items: [doneItem({ attempt: { outcome: "within_solid", submit_count: 1, used_template: "A" } })] });
      calls += 1;
      return Promise.resolve(today);
    });
    vi.mocked(postAttempt).mockResolvedValue(doneItem());

    renderToday();

    expect(await screen.findByText("题目 501")).toBeInTheDocument();
    expect(screen.queryByText(/今天做得怎么样/)).not.toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: "录入" }));
    expect(await screen.findByText(/今天做得怎么样/)).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /限时内做出来/ }));

    await waitFor(() => expect(postAttempt).toHaveBeenCalledTimes(1));
    // react-query's mutationFn is invoked with a second (context) argument
    // alongside the variables -- assert on the variables specifically.
    expect(vi.mocked(postAttempt).mock.calls[0][0]).toEqual({
      problem_id: 501,
      outcome: "within_solid",
      submit_count: 1,
      used_template: "A",
    });

    expect(await screen.findByRole("button", { name: "修改" })).toBeInTheDocument();
    expect(postAttempt).toHaveBeenCalledTimes(1);
  });

  it("shows 修改 on a done row, reopens prefilled, and a correction posts the updated values without duplicating", async () => {
    vi.mocked(fetchToday).mockResolvedValue(makeToday({ items: [doneItem()] }));
    vi.mocked(postAttempt).mockResolvedValue(doneItem());

    renderToday();

    expect(await screen.findByText(/已录入：没做出来/)).toBeInTheDocument();
    const editButton = screen.getByRole("button", { name: "修改" });
    fireEvent.click(editButton);

    // Prefilled with the recorded submit_count (2) and template (A), and
    // the currently-recorded outcome is visibly marked.
    expect(await screen.findByText("2")).toBeInTheDocument();
    expect(screen.getByText(/A ·/)).toBeInTheDocument();
    const currentButton = screen.getByRole("button", { name: /没做出来/ });
    expect(currentButton).toHaveAttribute("aria-pressed", "true");

    fireEvent.click(screen.getByRole("button", { name: /限时内做出来/ }));

    await waitFor(() => expect(postAttempt).toHaveBeenCalledTimes(1));
    expect(vi.mocked(postAttempt).mock.calls[0][0]).toEqual({
      problem_id: 501,
      outcome: "within_solid",
      submit_count: 2,
      used_template: "A",
    });
  });

  it("the submit_count stepper never submits and never goes below 1", async () => {
    vi.mocked(fetchToday).mockResolvedValue(makeToday({ items: [pendingItem()] }));

    renderToday();
    fireEvent.click(await screen.findByRole("button", { name: "录入" }));
    await screen.findByText(/今天做得怎么样/);

    const minus = screen.getByRole("button", { name: "减少提交次数" });
    const plus = screen.getByRole("button", { name: "增加提交次数" });

    fireEvent.click(minus);
    fireEvent.click(minus);
    fireEvent.click(minus);
    expect(screen.getByText("1", { selector: "span.font-mono" })).toBeInTheDocument();

    fireEvent.click(plus);
    fireEvent.click(plus);
    expect(screen.getByText("3", { selector: "span.font-mono" })).toBeInTheDocument();

    expect(postAttempt).not.toHaveBeenCalled();
  });

  it("shows both the recorded template and the derived one when they differ (规格 §5 R6)", async () => {
    vi.mocked(fetchToday).mockResolvedValue(
      makeToday({
        items: [
          doneItem({
            derived_template: "A",
            attempt: { outcome: "within_solid", submit_count: 1, used_template: "C" },
          }),
        ],
      }),
    );

    renderToday();
    fireEvent.click(await screen.findByRole("button", { name: "修改" }));

    expect(await screen.findByText(/C ·/)).toBeInTheDocument();
    expect(screen.getByText(/原本预期 A/)).toBeInTheDocument();
  });
});

describe("TodayPage -- fallback mode", () => {
  it("groups items by section when the plan has run out but problems remain", async () => {
    vi.mocked(fetchToday).mockResolvedValue(
      makeToday({
        is_fallback: true,
        phase: "",
        theme: "",
        items: [
          pendingItem({ problem: makeProblem({ id: 601, lc_id: 601, section: "§1.1", section_name: "定长滑动窗口 · 基础" }) }),
          pendingItem({ problem: makeProblem({ id: 602, lc_id: 602, section: "§1.2", section_name: "定长滑动窗口 · 进阶（选做）" }) }),
        ],
      }),
    );

    renderToday();

    // h3 section headings (distinct from each ProblemRow's own §-code
    // badge, which repeats the bare section code elsewhere on the page).
    expect(await screen.findByRole("heading", { level: 3, name: /§1\.1 定长滑动窗口 · 基础/ })).toBeInTheDocument();
    expect(screen.getByRole("heading", { level: 3, name: /§1\.2 定长滑动窗口 · 进阶（选做）/ })).toBeInTheDocument();
  });

  it("shows the finished-schedule message with the seed command when nothing is left", async () => {
    vi.mocked(fetchToday).mockResolvedValue(makeToday({ is_fallback: true, phase: "", theme: "", items: [] }));

    renderToday();

    expect(await screen.findByText(/本专题所有题都练完了/)).toBeInTheDocument();
    expect(screen.getByText(/leetcode_helper\.seed/)).toBeInTheDocument();
  });
});

describe("TodayPage -- error states", () => {
  it("shows a no-topic message on a 503 from /api/meta or /api/today", async () => {
    const { ApiError } = await vi.importActual<typeof import("../api/client")>("../api/client");
    vi.mocked(fetchToday).mockRejectedValue(new ApiError(503, "还没有导入任何 topic，先跑 python -m leetcode_helper.seed"));

    renderToday();

    expect(await screen.findByText("还没有可用的专题")).toBeInTheDocument();
  });
});
