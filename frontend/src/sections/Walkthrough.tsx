import { useEffect, useMemo, useState } from "react";

import { Section } from "@/components/chrome";
import { eventFailed, getJSON, patchFiles, type RunNode, type TaskRun } from "@/data";
import { Diff, layout } from "@/sections/Replay";

const FEATURED = "astropy__astropy-12907";
const GAP = 22;
const COL = 24;

/** Every attempt Forkfix grew on one bug, drawn as the tree it is. */
function BranchTree({ nodes, selected }: { nodes: RunNode[]; selected: string | null }) {
  const rows = useMemo(() => layout(nodes), [nodes]);
  const at = new Map(rows.map((r, i) => [r.node.id, i]));
  const depth = Math.max(...rows.map((r) => r.depth));
  const w = (depth + 1) * COL + 16;
  const h = rows.length * GAP + 12;
  const x = (d: number) => d * COL + 10;
  const y = (i: number) => i * GAP + 11;

  return (
    <svg
      viewBox={`0 0 ${w} ${h}`}
      width={w}
      height={h}
      role="img"
      aria-label={`${rows.length} attempts Forkfix grew on this bug, drawn as a tree. One was chosen as the answer.`}
      className="h-auto max-w-full text-ink"
    >
      <g fill="none" stroke="var(--color-rule-strong)" strokeWidth="1.5">
        {rows.map(({ node: n, depth: d }, i) => {
          const pi = n.parent == null ? undefined : at.get(n.parent);
          return pi == null ? null : <path key={n.id} d={`M${x(d - 1)} ${y(pi)} V${y(i)} H${x(d)}`} />;
        })}
      </g>
      {rows.map(({ node: n, depth: d }, i) => {
        const cx = x(d);
        const cy = y(i);
        if (n.id === selected) return <circle key={n.id} cx={cx} cy={cy} r="6.5" fill="var(--color-accent)" />;
        if (n.stop === "submitted") return <circle key={n.id} cx={cx} cy={cy} r="5" fill="currentColor" />;
        if (n.stop === "branched") return <circle key={n.id} cx={cx} cy={cy} r="4.5" fill="var(--color-paper)" stroke="currentColor" strokeWidth="1.8" />;
        if (n.stop === "step_limit")
          return <circle key={n.id} cx={cx} cy={cy} r="4.5" fill="var(--color-paper)" stroke="var(--color-mid)" strokeWidth="1.8" strokeDasharray="2 2" />;
        return <circle key={n.id} cx={cx} cy={cy} r="3.5" fill="var(--color-rule-strong)" />;
      })}
    </svg>
  );
}

const KEY = [
  ["bg-accent", "The attempt Forkfix chose"],
  ["bg-ink", "Another finished answer"],
  ["border-2 border-ink bg-paper", "Split into more attempts"],
  ["border-2 border-dashed border-mid bg-paper", "Ran out of steps"],
  ["bg-rule-strong", "Dropped"],
] as const;

export function Walkthrough() {
  const [run, setRun] = useState<TaskRun | null>(null);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    getJSON<TaskRun>(`/runs/${FEATURED}.json`)
      .then(setRun)
      .catch(() => setFailed(true));
  }, []);

  const f = run?.modes.branching;
  const one = run?.modes.linear;
  const win = f?.selected ? f.candidates[f.selected] : undefined;
  const pruned = f ? f.nodes.filter((n) => n.stop === "pruned").length : 0;
  const { lost, steps } = useMemo(() => {
    // how many of the one-try agent's final steps were edits that were rejected, back to back
    const ev = one?.nodes[0]?.events ?? [];
    let n = 0;
    for (let i = ev.length - 1; i >= 0 && ev[i].tool === "edit" && eventFailed(ev[i]); i--) n++;
    return { lost: n, steps: ev.length };
  }, [one]);

  if (failed || !run || !f || !win) return null;

  return (
    <Section
      id="walkthrough-title"
      anchor="example"
      title="One real bug, start to finish"
      lede="This is a real bug report from astropy, a Python library used by astronomers. Here is what happened when the same AI model worked on it two ways."
    >
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <ol className="space-y-8">
          <li>
            <h3 className="font-semibold">1. The bug report</h3>
            <p className="mt-2 max-w-[60ch] rounded-md bg-panel p-4 text-[15px]">
              &ldquo;separability_matrix does not compute separability correctly for nested CompoundModels&rdquo;
            </p>
            <p className="mt-2 max-w-[60ch] text-muted">
              In plain words: when you build a bigger model out of smaller ones, the library gives a wrong answer about
              which parts depend on each other. A developer reported it and asked for a fix.
            </p>
          </li>
          <li>
            <h3 className="font-semibold">2. One try, no Forkfix</h3>
            <p className="mt-2 max-w-[60ch] text-muted">
              The agent made a single attempt. {lost > 1 ? `For its last ${lost} of ${steps} steps, every edit it tried was rejected, because the text it wanted to replace was not in the file. ` : ""}
              It ran out of steps without fixing the bug.
            </p>
          </li>
          <li>
            <h3 className="font-semibold">3. With Forkfix</h3>
            <p className="mt-2 max-w-[60ch] text-muted">
              At its first edit, Forkfix split into three attempts, and kept splitting: {f.nodes.length} attempts in
              total. {pruned} were dropped after failing tests or looking weaker. The winner changes how the library
              combines nested models. It passes the {win.fail_to_pass[1] ?? "?"} tests written for this bug, and all{" "}
              {win.pass_to_pass[1] ?? "?"} of the library&rsquo;s existing tests still pass.
            </p>
            <details className="mt-3 max-w-[60ch]">
              <summary className="inline-flex min-h-9 cursor-pointer items-center text-sm underline underline-offset-4 hover:text-accent">
                See the actual code change
              </summary>
              <p className="num my-2 font-mono text-sm text-muted">{patchFiles(win.patch).map((p) => `${p.path} ${p.meta}`).join("  ·  ")}</p>
              <Diff patch={win.patch} />
            </details>
            <p className="mt-4">
              <a className="inline-flex min-h-9 items-center text-sm underline underline-offset-4 hover:text-accent" href="#replay">
                Step through every attempt on this bug
              </a>
            </p>
          </li>
        </ol>

        <figure className="lg:sticky lg:top-24 lg:self-start">
          <BranchTree nodes={f.nodes} selected={f.selected} />
          <figcaption className="mt-3 text-sm text-muted">
            <p>Each dot is one attempt Forkfix tried on this bug.</p>
            <ul className="mt-2 space-y-1">
              {KEY.map(([cls, label]) => (
                <li key={label} className="flex items-center gap-2">
                  <span aria-hidden className={`inline-block h-2.5 w-2.5 shrink-0 rounded-full ${cls}`} />
                  {label}
                </li>
              ))}
            </ul>
          </figcaption>
        </figure>
      </div>
    </Section>
  );
}
