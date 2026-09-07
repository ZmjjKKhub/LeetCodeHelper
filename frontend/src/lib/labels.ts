import type { Difficulty, DurationBucketValue } from "../api/types";

// leetcode_helper/models.py::Difficulty is a closed, non-topic-configurable
// 3-value enum -- unlike Outcome (whose Chinese labels come from
// /api/meta, see the task's "do not duplicate the strings" rule), the API
// never emits a Chinese label for it anywhere. Hardcoding one here mirrors
// what the server side already does for the equally-fixed DurationBucket
// enum in leetcode_helper/web/app_factory.py::BUCKET_LABELS.
export const DIFFICULTY_LABELS: Record<Difficulty, string> = {
  easy: "简单",
  medium: "中等",
  hard: "困难",
};

// design/tokens.css defines --easy/--medium/--hard once and the design
// artboards reuse those same three colours for both the difficulty bar/badge
// and the duration-bucket legend (限时内/超时/没做出来) -- so both mappings
// below target the same three Tailwind colour utilities.
export const DIFFICULTY_BAR_CLASSES: Record<Difficulty, string> = {
  easy: "bg-easy",
  medium: "bg-medium",
  hard: "bg-hard",
};

export const DIFFICULTY_TEXT_CLASSES: Record<Difficulty, string> = {
  easy: "text-easy",
  medium: "text-medium",
  hard: "text-hard",
};

// leetcode_helper/models.py::DurationBucket. Also not surfaced as a
// Chinese label by any endpoint (HistoryRowOut.duration_bucket is the raw
// enum value) -- same reasoning as DIFFICULTY_LABELS above.
export const BUCKET_LABELS: Record<DurationBucketValue, string> = {
  within: "限时内",
  over: "超时",
  unsolved: "没做出来",
};

export const BUCKET_CELL_CLASSES: Record<DurationBucketValue, string> = {
  within: "bg-easy",
  over: "bg-medium",
  unsolved: "bg-hard",
};

// services/attempts.py::Outcome -> the duration-bucket bucket it maps to
// (see split_outcome's _OUTCOME_TO_PAIR table). Used to colour a today-item
// cell in the progress grid and its outcome-button "current" state by the
// same three-colour legend the design uses for history rows, without the
// API needing to additionally expose duration_bucket on TodayItemOut.
export function outcomeBucket(outcome: string | null): DurationBucketValue | null {
  if (outcome === "within_solid" || outcome === "within_shaky") return "within";
  if (outcome === "over") return "over";
  if (outcome === "unsolved") return "unsolved";
  return null;
}

// Inverse of services/attempts.py::split_outcome's _OUTCOME_TO_PAIR table.
// HistoryRowOut only carries the raw (duration_bucket, mark) pair, not the
// derived 4-way Outcome -- the History page's "结论" column needs the
// latter (its label comes from /api/meta, same as everywhere else) to
// match design/History.dc.html, so the pair is mapped back to an Outcome
// value here, mirroring the server's own outcome_of().
const PAIR_TO_OUTCOME: Record<string, string> = {
  "within|A": "within_solid",
  "within|B": "within_shaky",
  "over|B": "over",
  "unsolved|C": "unsolved",
};

export function outcomeFromPair(bucket: DurationBucketValue, mark: string): string | null {
  return PAIR_TO_OUTCOME[`${bucket}|${mark}`] ?? null;
}

// Presentation-only colour per outcome for the entry panel's outcome
// buttons (the consequence text itself always comes from /api/meta -- this
// only picks which token renders it in). within_solid is the only outcome
// that schedules no review, so it alone gets the "good" colour.
export const OUTCOME_CONSEQUENCE_TEXT_CLASSES: Record<string, string> = {
  within_solid: "text-easy",
  within_shaky: "text-muted",
  over: "text-muted",
  unsolved: "text-alert",
};
