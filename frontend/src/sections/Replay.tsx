import { useEffect, useMemo, useState } from "react";

import { bugSummary, projectBlurb } from "@/bugs";
import { Section } from "@/components/chrome";
import {
  MODE_LABEL,
  ORDER,
  STOP_LABEL,
  TOOL_LABEL,
  bugLabel,
  bugTitle,
  eventFailed,
  fmtTokens,
  getJSON,
  patchFiles,
  setParam,
  sortRows,
  taskName,
  type IndexRow,
  type ModeName,
  type RunIndex,
  type RunNode,
  type TaskRun,
} from "@/data";

const cut = (s: string, n: number) => (s.length > n ? `${s.slice(0, n)}…` : s);

/** Depth-first order with a depth per node, so the branch list reads as the tree it is. */
export function layout(nodes: RunNode[]): { node: RunNode; depth: number }[] {
  const kids = new Map<string | null, RunNode[]>();
  for (const n of nodes) kids.set(n.parent, [...(kids.get(n.parent) ?? []), n]);
  const out: { node: RunNode; depth: number }[] = [];
  const walk = (parent: string | null, depth: number) => {
    for (const n of kids.get(parent) ?? []) {
      out.push({ node: n, depth });
      walk(n.id, depth + 1);
    }
  };
  walk(null, 0);
  const seen = new Set(out.map((o) => o.node.id));
  for (const n of nodes) if (!seen.has(n.id)) out.push({ node: n, depth: 0 });
  return out;
}

/** The branching-only win with the widest tree: the clearest first run to open. */
export function defaultTask(index: RunIndex): string {
  const wins = index.rows.filter((r) => r.modes.branching.solved && !r.modes.matched.solved && !r.modes.linear.solved);
  wins.sort((a, b) => b.modes.branching.branches - a.modes.branching.branches);
  return (wins[0] ?? index.rows[0]).task;
}

const MARK: Record<ModeName, string> = { branching: "bg-accent", matched: "bg-cool", linear: "bg-mid" };

function Marks({ row }: { row: IndexRow }) {
  return (
    <span className="flex gap-[3px]" aria-hidden>
      {(["branching", "matched", "linear"] as ModeName[]).map((m) => (
        <span key={m} className={`h-3 w-3 rounded-[2px] ${row.modes[m].solved ? MARK[m] : "bg-rule"}`} />
      ))}
    </span>
  );
}

export function Diff({ patch }: { patch: string }) {
  const lines = cut(patch, 8000).split("\n");
  return (
    <pre className="max-h-96 overflow-auto rounded-md border border-rule bg-panel py-2 font-mono text-[13px] leading-[1.55]">
      {lines.map((l, i) => {
        const add = l.startsWith("+") && !l.startsWith("+++");
        const del = l.startsWith("-") && !l.startsWith("---");
        return (
          <span
            key={i}
            className={`block min-w-max px-4 ${add ? "bg-add" : del ? "bg-accent-tint" : l.startsWith("@@") ? "text-muted" : ""}`}
          >
            {l || " "}
          </span>
        );
      })}
    </pre>
  );
}

const initialMode = (): ModeName => {
  const m = new URLSearchParams(window.location.search).get("mode");
  return ORDER.includes(m as ModeName) ? (m as ModeName) : "branching";
};

export function Replay({ index, task, onTask }: { index: RunIndex; task: string; onTask: (t: string) => void }) {
  const [mode, setMode] = useState<ModeName>(initialMode);
  const [node, setNode] = useState<string | null>(null);
  const [run, setRun] = useState<TaskRun | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [onlyWins, setOnlyWins] = useState(false);
  const [query, setQuery] = useState("");
  const [full, setFull] = useState(false);

  useEffect(() => {
    let live = true;
    setFailed(false);
    setNode(null);
    setFull(false);
    getJSON<TaskRun>(`/runs/${task}.json`)
      .then((r) => live && setRun(r))
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [task, retry]);

  useEffect(() => setParam("mode", mode === "branching" ? null : mode), [mode]);

  const sorted = useMemo(() => sortRows(index.rows), [index.rows]);
  const list = useMemo(() => {
    const q = query.trim().toLowerCase();
    return sorted.filter((r) => (!onlyWins || r.modes.branching.solved) && (!q || `${taskName(r.task)} ${bugSummary(r.task) ?? ""}`.toLowerCase().includes(q)));
  }, [sorted, onlyWins, query]);
  const at = list.findIndex((r) => r.task === task);

  // Keep showing nothing stale: the previous task's run is hidden until this task's run arrives.
  const cur = run && run.task === task ? run : null;
  const m = cur?.modes[mode];
  const tree = useMemo(() => (m ? layout(m.nodes) : []), [m]);
  const active: RunNode | undefined = m
    ? (m.nodes.find((n) => n.id === node) ?? m.nodes.find((n) => n.id === m.selected) ?? m.nodes[m.nodes.length - 1])
    : undefined;
  const cand = active && m ? m.candidates[active.id] : undefined;
  const changed = cand ? patchFiles(cand.patch) : [];
  const answer = m?.selected ? m.candidates[m.selected] : undefined;
  const outcome = !m
    ? ""
    : m.solved
      ? `${MODE_LABEL[mode]} fixed it. ${m.nodes.length > 1 ? `It tried ${m.nodes.length} attempts, and the one it chose passes the project's tests.` : "Its answer passes the project's tests."}`
      : answer
        ? `${MODE_LABEL[mode]} did not fix it. Its answer failed the project's tests.`
        : `${MODE_LABEL[mode]} did not fix it. It never reached an answer.`;

  const pickMode = (x: ModeName) => {
    setMode(x);
    setNode(null);
    setFull(false);
  };
  const onTabKey = (e: React.KeyboardEvent, i: number) => {
    if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return;
    e.preventDefault();
    const next = ORDER[(i + (e.key === "ArrowRight" ? 1 : ORDER.length - 1)) % ORDER.length];
    pickMode(next);
    document.getElementById(`tab-${next}`)?.focus();
  };

  const row = "flex min-h-11 w-full items-center gap-3 px-3 py-2 text-left text-sm transition-colors";
  const sel = (on: boolean) => (on ? "bg-accent-tint" : "hover:bg-panel");

  return (
    <Section
      id="replay-title"
      anchor="replay"
      stack
      band
      title="Explore all 79 bugs"
      lede="Pick a bug, read what went wrong in one line, and see whether each way of working fixed it."
    >
      <div className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)]">
        <div className="min-w-0">
          <label className="block">
            <span className="sr-only">Search bugs</span>
            <input
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search bugs, e.g. chart or pytest"
              className="min-h-11 w-full rounded-md border border-rule-strong bg-paper px-3 text-sm placeholder:text-muted"
            />
          </label>
          <div className="mt-2 flex items-center justify-between gap-3">
            <p className="num text-sm text-muted" role="status">
              {list.length} of {index.rows.length} bugs
            </p>
            <label className="flex min-h-11 cursor-pointer items-center gap-2 text-sm">
              <input type="checkbox" className="h-4 w-4 accent-[var(--color-accent)]" checked={onlyWins} onChange={(e) => setOnlyWins(e.target.checked)} />
              Forkfix fixed
            </label>
          </div>
          <ul className="max-h-56 overflow-y-auto border-y border-rule lg:max-h-[30rem]">
            {list.length === 0 ? (
              <li className="px-3 py-6 text-sm text-muted">
                No bug matches “{query}”.{" "}
                <button type="button" className="underline underline-offset-4 hover:text-accent" onClick={() => setQuery("")}>
                  Clear the filter
                </button>
              </li>
            ) : null}
            {list.map((r) => {
              const on = r.task === task;
              return (
                <li key={r.task} className="border-b border-rule last:border-b-0">
                  <button
                    type="button"
                    aria-current={on ? "true" : undefined}
                    onClick={() => onTask(r.task)}
                    className={`flex w-full items-start justify-between gap-3 px-3 py-3 text-left text-sm transition-colors ${sel(on)}`}
                  >
                    <span className="min-w-0">
                      <span className="block font-medium">{bugLabel(r.task)}</span>
                      <span className="mt-0.5 line-clamp-2 block text-[13px] text-muted">{bugSummary(r.task) ?? ""}</span>
                    </span>
                    <span className="mt-1 shrink-0">
                      <Marks row={r} />
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          <p className="mt-3 text-sm text-muted">
            The three squares on each row, left to right: Forkfix, independent tries, one try. A lit square means that way fixed the bug. Bugs Forkfix fixed come first.
          </p>
        </div>

        <div id="replay-detail" tabIndex={-1} className="min-w-0 outline-none">
          <p role="status" className="sr-only">
            {failed ? "This run did not load." : cur ? `Showing ${bugLabel(task)}.` : `Loading ${bugLabel(task)}.`}
          </p>
          {failed ? (
            <p role="alert" className="text-muted">
              This run did not load.{" "}
              <button type="button" className="underline underline-offset-4 hover:text-accent" onClick={() => setRetry((n) => n + 1)}>
                Try again
              </button>
            </p>
          ) : null}
          {!cur && !failed ? (
            <div aria-busy="true" className="space-y-3">
              <div className="h-6 w-2/3 rounded-sm bg-rule motion-safe:animate-pulse" />
              <div className="h-4 w-full rounded-sm bg-rule motion-safe:animate-pulse" />
              <div className="h-4 w-5/6 rounded-sm bg-rule motion-safe:animate-pulse" />
            </div>
          ) : null}

          {cur && m ? (
            <div className="space-y-8">
              <div>
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <p className="max-w-[40ch] text-[clamp(1.25rem,1rem+1vw,1.6rem)] font-semibold leading-snug tracking-tight">
                    {bugSummary(cur.task) ?? bugTitle(cur.problem)}
                  </p>
                  <div className="flex gap-1">
                    <button
                      type="button"
                      disabled={at <= 0}
                      onClick={() => onTask(list[at - 1].task)}
                      className="min-h-11 rounded-sm border border-rule-strong px-3 text-sm transition-colors enabled:hover:bg-panel disabled:text-muted disabled:opacity-60"
                    >
                      Previous bug
                    </button>
                    <button
                      type="button"
                      disabled={at < 0 || at >= list.length - 1}
                      onClick={() => onTask(list[at + 1].task)}
                      className="min-h-11 rounded-sm border border-rule-strong px-3 text-sm transition-colors enabled:hover:bg-panel disabled:text-muted disabled:opacity-60"
                    >
                      Next bug
                    </button>
                  </div>
                </div>
                <p className="mt-2 text-sm text-muted">
                  From {projectBlurb(cur.task).replace(": ", " (")})  · bug #{bugLabel(cur.task).split("#")[1]}
                </p>
                <details className="mt-2 max-w-[70ch]">
                  <summary className="inline-flex min-h-9 cursor-pointer items-center text-sm underline underline-offset-4 hover:text-accent">Read the original bug report</summary>
                  <p className="mt-2 text-sm font-medium">{bugTitle(cur.problem)}</p>
                  <p className="mt-1 whitespace-pre-line text-[15px] text-muted">{cut(cur.problem, 1200)}</p>
                </details>
              </div>

              <div>
                <h4 className="font-semibold">What happened when the AI tried to fix it</h4>
                <p className="mb-3 mt-1 text-sm text-muted">Same AI model each time. Pick a way of working to see its result.</p>
                <div role="tablist" aria-label="Way of working" className="grid gap-2 sm:grid-cols-3">
                  {ORDER.map((x, i) => {
                    const r = cur.modes[x];
                    return (
                      <button
                        key={x}
                        id={`tab-${x}`}
                        role="tab"
                        type="button"
                        aria-selected={x === mode}
                        aria-controls="replay-panel"
                        tabIndex={x === mode ? 0 : -1}
                        onKeyDown={(e) => onTabKey(e, i)}
                        onClick={() => pickMode(x)}
                        className={`min-h-11 rounded-md border px-3 py-2.5 text-left transition-colors ${
                          x === mode ? "border-ink bg-ink text-paper" : "border-rule-strong hover:bg-panel"
                        }`}
                      >
                        <span className="block text-sm font-medium">{MODE_LABEL[x]}</span>
                        <span className="mt-0.5 flex items-center gap-2 text-sm">
                          <span aria-hidden className={`inline-block h-3 w-3 rounded-[2px] ${r.solved ? MARK[x] : "bg-rule-strong"}`} />
                          {r.solved ? "Fixed it" : "Did not fix it"}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>

              <div id="replay-panel" role="tabpanel" aria-labelledby={`tab-${mode}`} className="space-y-6">
                <p className="max-w-[60ch]">{outcome}</p>

                <div>
                  <button
                    type="button"
                    aria-expanded={full}
                    aria-controls="replay-full"
                    onClick={() => setFull((v) => !v)}
                    className="min-h-11 rounded-md bg-ink px-4 text-sm font-medium text-paper transition-opacity hover:opacity-90"
                  >
                    {full ? "Hide the step-by-step" : "Explore this bug step by step"}
                  </button>
                  <p className="mt-2 text-sm text-muted">See every attempt the AI made, what it did at each step, and the exact code change.</p>
                </div>
                {full ? (
                  <div id="replay-full" className="mt-2 space-y-10">
                    <div>
                      <h4 className="mb-1 font-semibold">Attempts</h4>
                      <p className="mb-3 text-sm text-muted">
                        Each row is one attempt. Indented rows grew out of the row above them. Pick one to read its steps.
                      </p>
                      <ul className="divide-y divide-rule border-y border-rule">
                        {tree.map(({ node: n, depth }, idx) => {
                          const on = n.id === active?.id;
                          const c = m.candidates[n.id];
                          return (
                            <li key={n.id}>
                              <button
                                type="button"
                                aria-current={on ? "true" : undefined}
                                onClick={() => setNode(n.id)}
                                style={{ paddingLeft: 12 + depth * 20 }}
                                className={`grid min-h-11 w-full grid-cols-[minmax(0,1fr)_auto] items-center gap-x-4 py-2 pr-3 text-left text-sm transition-colors ${sel(on)}`}
                              >
                                <span className="flex min-w-0 items-baseline gap-2">
                                  {depth > 0 ? (
                                    <span aria-hidden className="text-rule-strong">
                                      └
                                    </span>
                                  ) : null}
                                  <span className="font-medium">Attempt {idx + 1}</span>
                                  <span className="truncate text-muted">{STOP_LABEL[n.stop] ?? n.stop}</span>
                                  {n.id === m.selected ? <span className="font-medium text-accent">chosen</span> : null}
                                </span>
                                <span className="num flex gap-4 text-sm text-muted">
                                  <span>{n.score == null ? "" : `reviewer ${n.score}/10`}</span>
                                  {c ? <span className={c.resolved ? "font-medium text-ink" : ""}>{c.resolved ? "passes the tests" : "fails the tests"}</span> : null}
                                </span>
                              </button>
                            </li>
                          );
                        })}
                      </ul>
                    </div>

                    {active ? (
                      <div>
                        <h4 className="font-semibold">Attempt {tree.findIndex((t) => t.node.id === active.id) + 1}</h4>
                        <p className="mt-1 text-sm text-muted">
                          Steps {active.born + 1} to {active.end}. This attempt {STOP_LABEL[active.stop] ?? active.stop}.
                        </p>

                        {cand ? (
                          <dl className="num mt-5 grid gap-x-8 gap-y-3 text-sm sm:grid-cols-3">
                            <div>
                              <dt className="text-muted">Tests for this bug</dt>
                              <dd className="mt-0.5 text-base font-medium">
                                {cand.fail_to_pass[0] ?? "?"} of {cand.fail_to_pass[1] ?? "?"} pass
                              </dd>
                            </div>
                            <div>
                              <dt className="text-muted">Existing tests still passing</dt>
                              <dd className="mt-0.5 text-base font-medium">
                                {cand.pass_to_pass[0] ?? "?"} of {cand.pass_to_pass[1] ?? "?"}
                              </dd>
                            </div>
                            <div>
                              <dt className="text-muted">AI reviewer score</dt>
                              <dd className="mt-0.5 text-base font-medium">{cand.judge == null ? "n/a" : `${cand.judge} / 10`}</dd>
                            </div>
                          </dl>
                        ) : null}
                        {cand?.existing_tests ? <p className="mt-4 text-sm text-muted">{cand.existing_tests}</p> : null}

                        <ol className="mt-6 divide-y divide-rule border-y border-rule">
                          {active.events.map((e) => (
                            <li key={e.step} className="py-3">
                              <div className="grid grid-cols-[44px_minmax(0,1fr)] gap-x-2 text-sm">
                                <span className="num text-sm text-muted">{e.step}</span>
                                <div className="min-w-0">
                                  <p>
                                    <span className="mr-2 rounded-sm bg-panel px-1.5 py-0.5 text-[13px] ring-1 ring-rule">{TOOL_LABEL[e.tool] ?? e.tool}</span>
                                    {eventFailed(e) ? <span className="mr-2 rounded-sm border border-ink px-1.5 py-0.5 text-[13px] font-medium">failed</span> : null}
                                    {cut(e.summary.replace(/^\w+:\s*/, "").replace("/testbed/", ""), 160)}
                                  </p>
                                  <details className="mt-1">
                                    <summary className="inline-flex min-h-9 cursor-pointer items-center text-sm text-muted hover:text-ink">What came back</summary>
                                    <pre className="mt-1 max-h-56 overflow-auto whitespace-pre-wrap rounded-md border border-rule bg-panel p-3 font-mono text-[13px] leading-[1.55]">
                                      {cut(e.observation, 500)}
                                    </pre>
                                  </details>
                                </div>
                              </div>
                            </li>
                          ))}
                        </ol>

                        {cand ? (
                          <div className="mt-8">
                            <h4 className="font-semibold">The code change</h4>
                            {changed.length ? (
                              <p className="num mb-3 mt-1 font-mono text-sm text-muted">{changed.map((f) => `${f.path} ${f.meta}`).join("  ·  ")}</p>
                            ) : null}
                            <Diff patch={cand.patch} />
                          </div>
                        ) : null}
                      </div>
                    ) : null}
                  </div>
                ) : null}
              </div>
            </div>
          ) : null}
        </div>
      </div>
    </Section>
  );
}
