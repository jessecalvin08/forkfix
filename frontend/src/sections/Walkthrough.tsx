import { useEffect, useMemo, useState } from "react";

import { Section } from "@/components/chrome";
import { eventFailed, getJSON, patchFiles, type RunNode, type TaskRun } from "@/data";
import { TreeView, type TreeNode } from "@/components/ui/animated-tree-view";
import { Diff } from "@/sections/Replay";

const FEATURED = "astropy__astropy-12907";
const SHORT: Record<string, string> = { branched: "split into more attempts", pruned: "dropped", submitted: "answer", step_limit: "out of steps", budget: "out of budget" };

/** Every attempt Forkfix grew on one bug, as a collapsible tree (21st.dev Animated Tree View). */
function BranchTree({ nodes, selected }: { nodes: RunNode[]; selected: string | null }) {
  const { data, open } = useMemo(() => {
    const num = new Map(nodes.map((n, i) => [n.id, i + 1]));
    const kids = new Map<string | null, RunNode[]>();
    for (const n of nodes) kids.set(n.parent, [...(kids.get(n.parent) ?? []), n]);
    const build = (n: RunNode): TreeNode => ({
      id: n.id,
      name: `Attempt ${num.get(n.id)} · ${n.id === selected ? "chosen" : (SHORT[n.stop] ?? n.stop)}${n.score != null ? ` · ${n.score}/10` : ""}`,
      children: (kids.get(n.id) ?? []).map(build),
    });
    return { data: (kids.get(null) ?? []).map(build), open: nodes.filter((n) => kids.has(n.id)).map((n) => n.id) };
  }, [nodes, selected]);

  return (
    <div className="max-h-[32rem] overflow-y-auto rounded-md border border-rule bg-panel p-2">
      <TreeView data={data} defaultExpandedIds={open} indent={16} />
    </div>
  );
}

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
      <div className="grid gap-10 lg:grid-cols-[minmax(0,1fr)_340px]">
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
            <p>Each row is one attempt. Open or close a split to follow the branches; the score is the AI reviewer&rsquo;s, where one was given.</p>
          </figcaption>
        </figure>
      </div>
    </Section>
  );
}
