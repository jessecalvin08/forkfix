import { useMemo, useState } from "react";

import BranchDetail from "./BranchDetail";
import TreeView from "./TreeView";
import { defaultNode, fmtTokens, shortTask } from "./tree";
import { useScrub, useTaskRun } from "./shared";
import { MODES, MODE_LABEL, type IndexRow, type ModeName, type RunIndex } from "./types";

export interface Route {
  task: string;
  mode: ModeName;
  node: string | null;
}

type Filter = "all" | "solved" | "only";

const FILTER_LABEL: Record<Filter, string> = { all: "All", solved: "Solved by any", only: "Branching only" };

const solvedAny = (r: IndexRow) => MODES.some((m) => r.modes[m].solved);
const branchingOnly = (r: IndexRow) => r.modes.branching.solved && !r.modes.matched.solved && !r.modes.linear.solved;

export default function Replay({ index, route, setRoute }: { index: RunIndex; route: Route; setRoute: (r: Route) => void }) {
  const [filter, setFilter] = useState<Filter>("all");
  const [query, setQuery] = useState("");
  const { run, failed } = useTaskRun(route.task);
  const modeRun = run ? run.modes[route.mode] : null;
  const maxStep = modeRun?.config.max_steps ?? 30;
  const { upTo, playing, play, scrub } = useScrub(maxStep, `${route.task}/${route.mode}`);
  const selectedNode = modeRun
    ? route.node && modeRun.nodes.some((n) => n.id === route.node)
      ? route.node
      : defaultNode(modeRun)
    : null;

  const counts: Record<Filter, number> = useMemo(
    () => ({ all: index.rows.length, solved: index.rows.filter(solvedAny).length, only: index.rows.filter(branchingOnly).length }),
    [index.rows],
  );

  const groups = useMemo(() => {
    const q = query.trim().toLowerCase();
    const keep = (r: IndexRow) =>
      (filter === "all" || (filter === "solved" ? solvedAny(r) : branchingOnly(r))) && (!q || r.task.toLowerCase().includes(q));
    const byRepo = new Map<string, IndexRow[]>();
    for (const r of [...index.rows].sort((a, b) => a.task.localeCompare(b.task, "en", { numeric: true })).filter(keep)) {
      byRepo.set(r.repo, [...(byRepo.get(r.repo) ?? []), r]);
    }
    return [...byRepo.entries()];
  }, [index.rows, filter, query]);
  const shown = groups.reduce((n, [, rows]) => n + rows.length, 0);

  return (
    <section className="section replay" id="replay" aria-labelledby="replay-title">
      <div className="wrap">
        <header className="section-head">
          <p className="stamp">Replay · all {index.tasks} tasks · three modes each</p>
          <h2 id="replay-title">Open any run and follow each branch to its verdict.</h2>
        </header>

        <div className="bench">
          <nav className="bench-list" aria-label="Benchmark tasks">
            <div className="filters" role="group" aria-label="Filter tasks">
              {(Object.keys(FILTER_LABEL) as Filter[]).map((f) => (
                <button key={f} className="seg-btn" aria-pressed={filter === f} onClick={() => setFilter(f)}>
                  {FILTER_LABEL[f]} <span className="mono dim">{counts[f]}</span>
                </button>
              ))}
            </div>
            <label className="search">
              <span className="visually-hidden">Search tasks</span>
              <input
                type="search"
                inputMode="search"
                autoComplete="off"
                placeholder="Search, e.g. sphinx-10325"
                value={query}
                onChange={(e) => setQuery(e.target.value)}
              />
            </label>

            <label className="task-select">
              <span className="stamp">Task</span>
              <select value={route.task} onChange={(e) => setRoute({ ...route, task: e.target.value, node: null })}>
                {[...index.rows]
                  .sort((a, b) => a.task.localeCompare(b.task, "en", { numeric: true }))
                  .map((r) => (
                    <option key={r.task} value={r.task}>
                      {shortTask(r.task)}
                      {r.modes.branching.solved ? " · branching solved" : ""}
                    </option>
                  ))}
              </select>
            </label>

            <div className="task-groups">
              <p className="stamp task-key" aria-hidden="true">
                <span>One · Matched · Branching</span>
              </p>
              {shown === 0 && <p className="empty">No task matches. Clear the search or pick another filter.</p>}
              {groups.map(([repo, rows]) => (
                <div key={repo} className="task-group">
                  <p className="stamp">{repo}</p>
                  <ul>
                    {rows.map((r) => (
                      <li key={r.task}>
                        <button
                          className="task-item"
                          aria-current={r.task === route.task ? "true" : undefined}
                          onClick={() => setRoute({ task: r.task, mode: route.mode, node: null })}
                        >
                          <span className="mono">{shortTask(r.task)}</span>
                          <span
                            className="pips"
                            role="img"
                            aria-label={MODES.map((m) => `${MODE_LABEL[m]} ${r.modes[m].solved ? "solved" : "not solved"}`).join(", ")}
                          >
                            {MODES.map((m) => (
                              <span key={m} className={`pip${r.modes[m].solved ? " fix" : ""}`} />
                            ))}
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </nav>

          <div className="bench-main">
            {failed && <p className="empty">This run did not load. Pick another task, or reload the page.</p>}
            {!failed && !run && <div className="skeleton tall" aria-busy="true" aria-label={`Loading ${route.task}`} />}
            {run && (
              <>
                <div className="run-head">
                  <p className="stamp">{run.repo}</p>
                  <h3 className="mono">{run.task}</h3>
                  <details className="issue">
                    <summary>The issue the agent was given</summary>
                    <pre>{run.problem}</pre>
                  </details>
                </div>

                <div className="mode-tabs" role="tablist" aria-label="Mode">
                  {MODES.map((m) => {
                    const mr = run.modes[m];
                    return (
                      <button
                        key={m}
                        role="tab"
                        id={`mode-${m}`}
                        aria-selected={route.mode === m}
                        aria-controls="mode-panel"
                        tabIndex={route.mode === m ? 0 : -1}
                        className="mode-tab"
                        onClick={() => setRoute({ ...route, mode: m, node: null })}
                        onKeyDown={(e) => {
                          const i = MODES.indexOf(route.mode);
                          const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
                          if (next === null) return;
                          e.preventDefault();
                          const target = MODES[(next + MODES.length) % MODES.length];
                          setRoute({ ...route, mode: target, node: null });
                          document.getElementById(`mode-${target}`)?.focus();
                        }}
                      >
                        <span className="mode-name">{MODE_LABEL[m]}</span>
                        <span className={`mode-verdict${mr.solved ? " fix" : ""}`}>{mr.solved ? "✓ solved" : "not solved"}</span>
                        <span className="mode-cost mono">
                          {fmtTokens(mr.tokens)} tokens · {mr.sandbox_runs} runs
                        </span>
                      </button>
                    );
                  })}
                </div>

                {modeRun && selectedNode && (
                  <div role="tabpanel" id="mode-panel" aria-labelledby={`mode-${route.mode}`} className="mode-panel">
                    <div className="scrubber">
                      <button className="btn btn-sm" onClick={play}>
                        {playing ? "Pause" : upTo >= maxStep ? "Replay from 0" : "Play"}
                      </button>
                      <label className="scrub">
                        <span className="stamp">
                          Step {upTo} of {maxStep}
                        </span>
                        <input type="range" min={0} max={maxStep} value={upTo} onChange={(e) => scrub(Number(e.target.value))} />
                      </label>
                    </div>

                    <div className="tree-scroll" tabIndex={0} role="region" aria-label="Branch tree, scrollable">
                      <TreeView
                        mode={route.mode}
                        run={modeRun}
                        upTo={upTo}
                        selected={selectedNode}
                        onSelect={(id) => setRoute({ ...route, node: id })}
                      />
                    </div>
                    <Legend />
                    <BranchDetail mode={route.mode} run={modeRun} nodeId={selectedNode} />
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </section>
  );
}

function Legend() {
  return (
    <ul className="legend" aria-label="Legend">
      <li>Steps run left to right.</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><line className="mark" x1="7" x2="7" y1="2" y2="12" /></svg> shell command</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><circle className="mark hollow" cx="7" cy="7" r="2.6" /></svg> read a file</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><rect className="mark solid" x="3.5" y="3.5" width="7" height="7" transform="rotate(45 7 7)" /></svg> edit or create</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><circle className="fork-dot" cx="7" cy="7" r="4.5" /></svg> fork: snapshot copied</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><line className="end-bar" x1="7" x2="7" y1="0" y2="14" /></svg> pruned by the judge</li>
      <li><span className="swatch fix" aria-hidden="true" /> route to a patch that passed the hidden tests</li>
    </ul>
  );
}
