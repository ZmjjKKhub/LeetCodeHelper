// Mirrors leetcode_helper/api/schemas.py::MetaOut and its nested types.
// Kept hand-written and minimal for now (scaffolding only) rather than
// generated -- revisit once more endpoints are wired up.

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
