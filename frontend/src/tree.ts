import type { ModeRun, RunEvent, RunNode } from "./types";

export interface Placed {
  node: RunNode;
  row: number;
  /** Row of the parent at the fork, for the connector; null for a root. */
  parentRow: number | null;
  /** Step at which the first passing patch below this node finished; null if none did. */
  fixAt: number | null;
  resolved: boolean | null; // null: not a graded candidate
  selected: boolean;
}

/**
 * Git-graph layout: the first child continues its parent's row, later children take
 * the next free row. Depth-first, so a subtree's rows stay together and a connector
 * never crosses a segment that has already started.
 */
export function layout(run: ModeRun): { placed: Placed[]; rows: number } {
  const children = new Map<string | null, RunNode[]>();
  for (const n of run.nodes) {
    const list = children.get(n.parent) ?? [];
    list.push(n);
    children.set(n.parent, list);
  }
  const byId = new Map(run.nodes.map((n) => [n.id, n]));
  const fixAt = new Map<string, number>();
  for (const [id, c] of Object.entries(run.candidates)) {
    const leaf = byId.get(id);
    if (!c.resolved || !leaf) continue;
    for (let cur: RunNode | undefined = leaf; cur; cur = cur.parent ? byId.get(cur.parent) : undefined) {
      fixAt.set(cur.id, Math.min(fixAt.get(cur.id) ?? Infinity, leaf.end));
    }
  }

  const placed: Placed[] = [];
  let next = 0;
  const place = (n: RunNode, row: number, parentRow: number | null) => {
    const cand = run.candidates[n.id];
    placed.push({
      node: n,
      row,
      parentRow,
      fixAt: fixAt.get(n.id) ?? null,
      resolved: cand ? cand.resolved : null,
      selected: run.selected === n.id,
    });
    (children.get(n.id) ?? []).forEach((kid, i) => place(kid, i === 0 ? row : next++, row));
  };
  for (const root of children.get(null) ?? []) place(root, next++, null);
  return { placed, rows: next };
}

/** Every event on the path from the root to `id`, each tagged with the node that ran it. */
export function lineage(run: ModeRun, id: string): { node: RunNode; events: RunEvent[] }[] {
  const byId = new Map(run.nodes.map((n) => [n.id, n]));
  const path: RunNode[] = [];
  for (let cur = byId.get(id); cur; cur = cur.parent ? byId.get(cur.parent) : undefined) path.unshift(cur);
  return path.map((node) => ({ node, events: node.events }));
}

export function defaultNode(run: ModeRun): string {
  if (run.selected) return run.selected;
  const leaves = run.nodes.filter((n) => n.stop !== "branched");
  return (leaves.sort((a, b) => b.end - a.end)[0] ?? run.nodes[0]).id;
}

export function stopWords(node: RunNode, resolved: boolean | null): string {
  if (resolved === true) return "passed hidden tests";
  if (resolved === false) return node.stop === "submitted" ? "submitted, failed hidden tests" : "patch failed hidden tests";
  switch (node.stop) {
    case "branched":
      return "forked";
    case "submitted":
      return "submitted, no patch";
    case "pruned":
      return node.score === null ? "pruned" : `pruned, judge ${fmtScore(node.score)}`;
    case "step_limit":
      return "step limit, no patch";
    case "budget":
      return "token budget spent, no patch";
    default:
      return "stopped: no valid action";
  }
}

/** The tree's row label: short enough to sit beside 30 steps. */
export function shortStop(node: RunNode, resolved: boolean | null): string {
  if (resolved !== null) return resolved ? "✓ passed" : "✗ failed";
  switch (node.stop) {
    case "pruned":
      return node.score === null ? "pruned" : `pruned · judge ${fmtScore(node.score)}`;
    case "step_limit":
      return "step limit · no patch";
    case "budget":
      return "budget spent · no patch";
    case "submitted":
      return "no patch";
    default:
      return "no valid action";
  }
}

export function fmtScore(score: number): string {
  return `${Number.isInteger(score) ? score : score.toFixed(1)}/10`;
}

export function fmtTokens(n: number): string {
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${Math.round(n / 1e3)}K`;
  return String(n);
}

export function shortTask(task: string): string {
  const [, rest] = task.split("__");
  return rest ?? task;
}
