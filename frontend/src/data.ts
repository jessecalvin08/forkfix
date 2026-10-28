// Shapes written by backend/forkfix/viewer_data.py (runs/) and export_real_issues (fix/).

export type ModeName = "linear" | "matched" | "branching";
export const MODES: ModeName[] = ["linear", "matched", "branching"];
export const MODE_LABEL: Record<ModeName, string> = {
  linear: "One try",
  matched: "Independent tries",
  branching: "Forkfix",
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
  benchmark: { sources: { file: string; seed: number; created: string }[] } | { seed: number; created: string };
  forks: { tasks_with_forks: number; forks: number; divergent_forks: number; decisive_forks: number; branching_wins: number };
  rows: IndexRow[];
}

export interface IssueCandidate {
  id: string;
  stop: string;
  steps: number;
  judge: number | null;
  proven: boolean;
  reproduction: string | null;
  existing_tests: string | null;
  patch: string;
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
  clean: boolean;
  review: string | null;
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

export async function getJSON<T>(url: string): Promise<T> {
  const r = await fetch(url, { cache: "no-cache" });
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json() as Promise<T>;
}

export const fmtTokens = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)}M` : n >= 1e3 ? `${Math.round(n / 1e3)}k` : String(n));
export const usd = (n: number | null) => (n == null ? "n/a" : `$${n.toFixed(2)}`);
export const fmtP = (p: number) => `p = ${p.toFixed(3)}`;

/** A step failed when the shell exited non-zero or the tool reported an error. */
export function eventFailed(e: RunEvent): boolean {
  if (e.observation.startsWith("Error:")) return true;
  const m = /^\[exit code (\d+)\]/.exec(e.observation);
  return m ? m[1] !== "0" : false;
}

/** Changed files with +/- line counts from a unified diff. */
export function patchFiles(patch: string): { path: string; meta: string }[] {
  const files: { path: string; add: number; del: number }[] = [];
  for (const line of patch.split("\n")) {
    if (line.startsWith("diff --git ")) {
      const m = / b\/(.+)$/.exec(line);
      files.push({ path: m ? m[1] : line.slice(11), add: 0, del: 0 });
    } else if (files.length && line.startsWith("+") && !line.startsWith("+++")) files[files.length - 1].add++;
    else if (files.length && line.startsWith("-") && !line.startsWith("---")) files[files.length - 1].del++;
  }
  return files.map((f) => ({ path: f.path, meta: `+${f.add} −${f.del}` }));
}

export const STOP_LABEL: Record<string, string> = {
  branched: "split into more attempts",
  pruned: "dropped",
  submitted: "submitted as an answer",
  step_limit: "ran out of steps",
  budget: "ran out of budget",
};

export const TOOL_LABEL: Record<string, string> = {
  view: "Read a file",
  create: "Created a file",
  edit: "Edited a file",
  bash: "Ran a command",
  submit: "Submitted",
};

/** "astropy__astropy-12907" -> "astropy #12907": a name and a number a person can say out loud. */
export function bugLabel(task: string): string {
  const tail = task.split("__")[1] ?? task;
  const i = tail.lastIndexOf("-");
  return i < 0 ? tail : `${tail.slice(0, i)} #${tail.slice(i + 1)}`;
}

/** The first line of the bug report, which is its title. */
export function bugTitle(problem: string): string {
  const line = problem.split("\n").find((l) => l.trim()) ?? problem;
  const t = line.replace(/`/g, "").trim();
  return t.length > 140 ? `${t.slice(0, 140)}…` : t;
}

export const ORDER: ModeName[] = ["branching", "matched", "linear"];
export const taskName = (id: string) => id.replace("__", "/");

/** Tasks branching solved first, then matched, then one attempt; ties by name. A column keeps one task. */
export function sortRows(rows: IndexRow[]): IndexRow[] {
  const key = (r: IndexRow) => ORDER.map((m) => (r.modes[m].solved ? 1 : 0));
  return [...rows].sort((a, b) => {
    const x = key(a);
    const y = key(b);
    for (let i = 0; i < x.length; i++) if (x[i] !== y[i]) return y[i] - x[i];
    return a.task.localeCompare(b.task);
  });
}

/** Mirror one piece of viewer state into the address bar without adding history entries. */
export function setParam(key: string, value: string | null) {
  try {
    const u = new URL(window.location.href);
    if (value == null) u.searchParams.delete(key);
    else u.searchParams.set(key, value);
    window.history.replaceState(null, "", u);
  } catch {
    /* the address bar is a convenience, not state the page depends on */
  }
}
