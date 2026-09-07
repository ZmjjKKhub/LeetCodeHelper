import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import type { HistoryRowOut } from "../api/types";
import { META, makeHistory, makeProblem } from "../test/fixtures";
import { HistoryPage } from "./History";

vi.mock("../api/client", async () => {
  const actual = await vi.importActual<typeof import("../api/client")>("../api/client");
  return {
    ...actual,
    fetchMeta: vi.fn(),
    fetchHistory: vi.fn(),
  };
});

import { fetchHistory, fetchMeta } from "../api/client";

function renderHistory() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter>
        <HistoryPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.mocked(fetchMeta).mockResolvedValue(META);
});

describe("HistoryPage", () => {
  it("renders the four stat tiles and groups records by date", async () => {
    const rows: HistoryRowOut[] = [
      {
        date: "2026-09-02",
        problem: makeProblem({ id: 1, lc_id: 209, title: "长度最小的子数组" }),
        duration_bucket: "unsolved",
        mark: "C",
        submit_count: 1,
        used_template: "C",
        first_try_ac: false,
      },
      {
        date: "2026-09-02",
        problem: makeProblem({ id: 2, lc_id: 643, title: "子数组最大平均数 I" }),
        duration_bucket: "within",
        mark: "A",
        submit_count: 1,
        used_template: "A",
        first_try_ac: true,
      },
      {
        date: "2026-09-01",
        problem: makeProblem({ id: 3, lc_id: 1052, title: "爱生气的书店老板", section: "§1.2" }),
        duration_bucket: "over",
        mark: "B",
        submit_count: 2,
        used_template: null,
        first_try_ac: false,
      },
    ];
    vi.mocked(fetchHistory).mockResolvedValue(makeHistory({ rows }));

    renderHistory();

    // 总记录 3, 一次 AC 率 33% (1/3), C 类占比 33% (1/3 marks are C), 练习天数 2
    expect(await screen.findByText("总记录")).toBeInTheDocument();
    expect(screen.getByText("总记录").previousElementSibling?.textContent).toBe("3");
    expect(screen.getByText("一次 AC 率").previousElementSibling?.textContent).toBe("33%");
    expect(screen.getByText("C 类占比").previousElementSibling?.textContent).toBe("33%");
    expect(screen.getByText("练习天数").previousElementSibling?.textContent).toBe("2");

    const day1 = await screen.findByTestId("history-day-2026-09-02");
    expect(within(day1).getByText("长度最小的子数组")).toBeInTheDocument();
    expect(within(day1).getByText("子数组最大平均数 I")).toBeInTheDocument();
    expect(within(day1).queryByText("爱生气的书店老板")).not.toBeInTheDocument();

    const day2 = screen.getByTestId("history-day-2026-09-01");
    expect(within(day2).getByText("爱生气的书店老板")).toBeInTheDocument();
    expect(within(day2).queryByText("长度最小的子数组")).not.toBeInTheDocument();
  });

  it("shows the empty state when there are no records yet", async () => {
    vi.mocked(fetchHistory).mockResolvedValue(makeHistory());

    renderHistory();

    expect(await screen.findByText("还没有任何做题记录。")).toBeInTheDocument();
  });

  it("shows a no-topic message on a 503", async () => {
    const { ApiError } = await vi.importActual<typeof import("../api/client")>("../api/client");
    vi.mocked(fetchHistory).mockRejectedValue(new ApiError(503, "还没有导入任何 topic"));

    renderHistory();

    expect(await screen.findByText("还没有可用的专题")).toBeInTheDocument();
  });
});
