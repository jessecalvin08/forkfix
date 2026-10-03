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
  /** One task list, or several pooled non-overlapping ones (each with its own seed and date). */
  benchmark: { seed: number; created: string } | { sources: { file: string; seed: number; created: string }[] };
  /** From forkfix.forks: what the forks did in the branching runs. */
  forks: {
    tasks_with_forks: number;
    forks: number;
    divergent_forks: number;
    decisive_forks: number;
    decisive_where_own_action_failed: number;
    branching_wins: number;
    wins_where_own_path_also_passed: number;
    wins_needing_an_alternative: string[];
  };
  rows: IndexRow[];
}

// Real GitHub issues (backend/forkfix/fix.py), written by export_real_issues in viewer_data.py.
export interface IssueCandidate {
  id: string;
  stop: string;
  steps: number;
  judge: number | null;
  /** The agent's own reproduction test failed on the unfixed repo and passed on this branch. */
  proven: boolean;
  reproduction: string | null;
  existing_tests: string | null;
  patch: string;
  /** The repository's own tests that passed before now fail on this branch. */
  regressions: boolean;
}

export interface RealIssue {
  issue: string;
  url: string;
  title: string;
  run: string;
  commit: string;
  max_steps: number;
  tokens: number;
  sandbox_runs: number;
  selected: string | null;
  proven: boolean;
  /** The selected branch is proven and breaks no existing test. */
  clean: boolean;
  candidates: IssueCandidate[];
  note: string | null;
}

export interface RealIssueIndex {
  issues: number;
  proven: number;
  clean: number;
  patched: number;
  tokens: number;
  rows: RealIssue[];
}
