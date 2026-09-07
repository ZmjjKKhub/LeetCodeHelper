// Mirrors leetcode_helper/api/schemas.py and its nested types. Kept
// hand-written (not generated) -- see the note in the original scaffolding
// version of this file.

export interface TopicOut {
  code: string;
  name: string;
}

export interface TemplateOut {
  code: string;
  name: string;
  trigger_signal: string;
}

export interface OutcomeOut {
  value: string;
  label: string;
  consequence: string;
}

export interface MetaOut {
  topic: TopicOut;
  templates: TemplateOut[];
  outcomes: OutcomeOut[];
}

// leetcode_helper/models.py::Difficulty. A closed 3-value enum, not
// topic-configurable -- unlike Outcome (whose labels come from /api/meta),
// there is no API-exposed Chinese label for this, so DIFFICULTY_LABELS in
// lib/labels.ts hardcodes one, same as app_factory.py's own BUCKET_LABELS
// does server-side for DurationBucket.
export type Difficulty = "easy" | "medium" | "hard";

// leetcode_helper/models.py::DurationBucket.
export type DurationBucketValue = "within" | "over" | "unsolved";

export interface ProblemOut {
  id: number;
  lc_id: number;
  title: string;
  url: string;
  difficulty: Difficulty;
  section: string;
  section_name: string;
  is_starred: boolean;
  is_optional: boolean;
}

export interface AttemptOut {
  // null when the stored (duration_bucket, mark) pair predates the current
  // four-option UI and cannot be mapped back onto one Outcome value -- see
  // services/attempts.py::outcome_of.
  outcome: string | null;
  submit_count: number;
  used_template: string | null;
}

export interface TodayItemOut {
  problem: ProblemOut;
  time_limit_sec: number;
  is_done: boolean;
  derived_template: string | null;
  attempt: AttemptOut | null;
}

export interface TodayOut {
  topic: TopicOut;
  date: string;
  is_fallback: boolean;
  phase: string;
  theme: string;
  items: TodayItemOut[];
}

export interface HistoryRowOut {
  date: string;
  problem: ProblemOut;
  duration_bucket: DurationBucketValue;
  mark: string;
  submit_count: number;
  used_template: string | null;
  first_try_ac: boolean;
}

export interface HistoryOut {
  rows: HistoryRowOut[];
  limit: number;
  truncated: boolean;
}

export interface AttemptCreateIn {
  problem_id: number;
  outcome: string;
  submit_count?: number;
  used_template?: string | null;
}

// leetcode_helper/api/schemas.py::ProgressPlanOut. Present only when `today`
// falls inside an active plan's PlanDay -- null in fallback mode.
export interface ProgressPlanOut {
  day_index: number;
  total_days: number;
  phase: string;
  planned_date: string;
}

// leetcode_helper/api/schemas.py::ProgressProblemOut.
export interface ProgressProblemOut {
  lc_id: number;
  title: string;
  state: "done" | "today" | "todo";
  // Same None-when-unmappable rule as AttemptOut.outcome; always null when
  // state !== "done".
  outcome: string | null;
}

export interface ProgressSectionOut {
  section: string;
  section_name: string;
  total: number;
  done: number;
  problems: ProgressProblemOut[];
}

export interface ProgressStatsOut {
  total: number;
  attempted: number;
  unsolved: number;
  first_try_ac_count: number;
  // Fraction in [0, 1] -- the frontend formats it as a percentage.
  first_try_ac_rate: number;
}

export interface ProgressOut {
  topic: TopicOut;
  plan: ProgressPlanOut | null;
  sections: ProgressSectionOut[];
  stats: ProgressStatsOut;
}
