import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { MetaOut } from "../api/types";
import { SmokePage } from "./Smoke";

// One real test proving the smoke page's actual rendering logic (not just
// "it mounts"): given a /api/meta-shaped response, it must show the topic
// name and every outcome label -- the same claim the curl-based manual
// verification in the task makes, just runnable in CI without a live
// server. fetch is mocked here (Vitest's jsdom env has no network), so
// this does not replace the real build -> serve -> fetch chain check.
const META: MetaOut = {
  topic: { code: "sliding-window", name: "滑动窗口" },
  templates: [],
  outcomes: [
    { value: "within_solid", label: "限时内-扎实", consequence: "" },
    { value: "within_shaky", label: "限时内-勉强", consequence: "" },
    { value: "over", label: "超时", consequence: "" },
    { value: "unsolved", label: "没做出来", consequence: "" },
  ],
};

function renderWithProviders(ui: React.ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>{ui}</QueryClientProvider>,
  );
}

describe("SmokePage", () => {
  beforeEach(() => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => ({
        ok: true,
        json: async () => META,
      })),
    );
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the topic name and all four outcome labels from /api/meta", async () => {
    renderWithProviders(<SmokePage />);

    expect(await screen.findByText("滑动窗口")).toBeInTheDocument();
    for (const outcome of META.outcomes) {
      expect(screen.getByText(outcome.label)).toBeInTheDocument();
    }
    await waitFor(() => expect(fetch).toHaveBeenCalledWith("/api/meta"));
  });
});
