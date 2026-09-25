// Shapes written by backend/forkfix/viewer_data.py.

export type ModeName = "linear" | "matched" | "branching";

export const MODES: ModeName[] = ["linear", "matched", "branching"];

export const MODE_LABEL: Record<ModeName, string> = {
  linear: "One attempt",
  matched: "Matched attempts",
  branching: "Branching",
};

export interface RunEvent {
  step: number;
  tool: string;
  summary: string;
  observation: string;
  snapshot: string;
}

export interface RunNode {
  id: string;
  parent: string | null;
  born: number;
  end: number;
  stop: string;
  score: number | null;
  events: RunEvent[];
}

export interface Candidate {
  resolved: boolean;
  judge: number | null;
  existing_tests: string | null;
  broken: boolean;
  regressions: number | null;
  fail_to_pass: [number | null, number | null];
  pass_to_pass: [number | null, number | null];
  patch: string;
}

export interface ModeRun {
  solved: boolean;
  any_candidate: boolean;
  selected: string | null;
  attempts: number | null;
  token_budget: number | null;
  tokens: number;
  sandbox_runs: number;
  wall_seconds: number | null;
  config: { width: number; branch_factor: number; max_branch_points: number; max_steps: number };
  nodes: RunNode[];
  candidates: Record<string, Candidate>;
}

export interface TaskRun {
  task: string;
  repo: string;
  problem: string;
  modes: Record<ModeName, ModeRun>;
}

export interface Totals {
  solved: number;
  any_candidate: number;
  tokens: number;
  sandbox_runs: number;
  /** List-price estimate from forkfix.report; null if a model had no known price. */
  estimated_usd: number | null;
}

export interface IndexRow {
  task: string;
  repo: string;
  modes: Record<ModeName, { solved: boolean; any_candidate: boolean; tokens: number; forks: number; branches: number }>;
}

export interface RunIndex {
  tasks: number;
  totals: Record<ModeName, Totals>;
  comparisons: {
    branching_vs_linear: { only_branching: number; only_linear: number; mcnemar_p: number };
    branching_vs_matched: { only_branching: number; only_matched: number; mcnemar_p: number };
  };
  benchmark: { seed: number; created: string };
  rows: IndexRow[];
}
