import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

// vite.config.ts's `test` block does not set `globals: true` (every test
// file imports describe/it/expect/vi from "vitest" explicitly instead), so
// @testing-library/react's own auto-cleanup -- which only registers itself
// when it detects a *global* afterEach -- never fires. Without this, render()
// output from every test in a file accumulates in the same jsdom document,
// and a later test's queries (getByRole, etc.) can match leftover elements
// from an earlier one. Register it explicitly here instead, once, for every
// test file.
afterEach(() => {
  cleanup();
});
