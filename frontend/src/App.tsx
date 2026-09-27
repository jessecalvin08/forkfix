import { useEffect, useMemo, useRef, useState } from "react";

import BranchDetail from "./BranchDetail";
import TreeView from "./TreeView";
import { defaultNode, fmtTokens, shortTask } from "./tree";
import { MODES, MODE_LABEL, type IndexRow, type ModeName, type RunIndex, type TaskRun } from "./types";

const REPO_URL = "https://github.com/jessecalvin08/forkfix";

interface Route {
  task: string;
  mode: ModeName;
  node: string | null;
}

function readHash(): Partial<Route> {
  const [task, mode, node] = decodeURIComponent(location.hash.slice(1)).split("/");
  return {
    task: task || undefined,
    mode: MODES.includes(mode as ModeName) ? (mode as ModeName) : undefined,
    node: node || null,
  };
}

/** The branching-only win with the widest tree: the clearest first thing to show. */
function pickDefault(rows: IndexRow[]): string {
  const wins = rows.filter((r) => r.modes.branching.solved && !r.modes.matched.solved && !r.modes.linear.solved);
  wins.sort((a, b) => b.modes.branching.branches - a.modes.branching.branches);
  return (wins[0] ?? rows[0]).task;
}

export default function App() {
  const [index, setIndex] = useState<RunIndex | null>(null);
  const [failed, setFailed] = useState(false);
  const [route, setRoute] = useState<Route | null>(null);

  useEffect(() => {
    fetch("/runs/index.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: RunIndex) => {
        setIndex(data);
        const hash = readHash();
        const known = data.rows.some((r) => r.task === hash.task);
        setRoute({
          task: known ? hash.task! : pickDefault(data.rows),
          mode: hash.mode ?? "branching",
          node: known ? (hash.node ?? null) : null,
        });
      })
      .catch(() => setFailed(true));
  }, []);

  useEffect(() => {
    if (!route) return;
    const hash = `#${route.task}/${route.mode}${route.node ? `/${route.node}` : ""}`;
    if (location.hash !== hash) history.replaceState(null, "", hash);
  }, [route]);

  return (
    <div className="shell">
      <a className="skip-link" href="#replay">Skip to the run replay</a>
      <Masthead />
      <main>
        {failed && <p className="load-error">The run data did not load. Reload the page to try again.</p>}
        {index && route && (
          <>
            <Results
              index={index}
              onOpen={(task) => {
                setRoute({ task, mode: "branching", node: null });
                document.getElementById("replay")?.scrollIntoView({ block: "start" });
              }}
            />
            <Replay index={index} route={route} setRoute={setRoute} />
          </>
        )}
        <Method />
      </main>
      <footer className="footer">
        <div className="wrap">
          <p>
            Forkfix, a solo entry to the Nebius × NVIDIA Global AI Hackathon (Coding &amp; Agentic Engineering).
            Every number on this page is generated from saved run reports by{" "}
            <code>forkfix.report</code> and <code>forkfix.viewer_data</code>.
          </p>
          <a href={REPO_URL}>Source on GitHub</a>
        </div>
      </footer>
    </div>
  );
}

function Masthead() {
  return (
    <header className="masthead">
      <div className="wrap">
        <div className="masthead-bar">
          <span className="wordmark">
            <ForkMark /> Forkfix
          </span>
          <span className="nameplate">Nebius Sandboxes · NVIDIA Nemotron</span>
        </div>
        <h1>A coding agent that forks its sandbox before changing code, then submits the strongest branch.</h1>
        <p className="lede">
          Every step the agent takes runs in a Nebius Sandbox snapshot. When its next action would edit a file,
          Forkfix samples two alternatives and runs each in its own copy of that snapshot. A judge model prunes the
          weakest branches, and the best surviving patch is submitted. The agent is NVIDIA Nemotron 3 Nano
          (3B active parameters); the judge is Nemotron 3 Super.
        </p>
      </div>
    </header>
  );
}

function ForkMark() {
  return (
    <svg className="fork-mark" viewBox="0 0 20 20" aria-hidden="true">
      <path d="M3 10 H8 M8 10 C11 10 11 4 14 4 H17 M8 10 H17 M8 10 C11 10 11 16 14 16 H17" />
      <circle cx="8" cy="10" r="2" />
    </svg>
  );
}

function Results({ index, onOpen }: { index: RunIndex; onOpen: (task: string) => void }) {
  const { totals, comparisons: cmp } = index;
  const solvedRows = index.rows.filter((r) => MODES.some((m) => r.modes[m].solved));
  const pct = (n: number) => {
    const v = (100 * n) / index.tasks;
    return `${Number.isInteger(v) ? v : v.toFixed(1)}%`;
  };
  const branchingUsd = totals.branching.estimated_usd;
  const perTask = branchingUsd == null ? null : branchingUsd / index.tasks;
  const allModes = MODES.some((m) => totals[m].estimated_usd == null)
    ? null
    : MODES.reduce((sum, m) => sum + (totals[m].estimated_usd ?? 0), 0);
  const note: Record<ModeName, string> = {
    linear: "The ordinary agent: one trajectory, temperature 0.",
    matched: "Independent attempts, four at a time, given the tokens branching spent on the same task.",
    branching: "Forks at code changes, at most three fork points on any path, at most four branches alive.",
  };
  return (
    <section className="results" aria-labelledby="results-title">
      <div className="wrap">
        <p className="nameplate">Benchmark · {index.tasks} held-out SWE-bench Lite tasks · run {runDates(index.benchmark)}</p>
        <h2 id="results-title">
          Branching fixed {totals.branching.solved} of {index.tasks} bugs. Independent attempts with the same token
          budget fixed {totals.matched.solved}.
        </h2>

        <div className="table-scroll">
          <table className="totals">
            <thead>
              <tr>
                <th scope="col">Mode, all Nemotron 3 Nano</th>
                <th scope="col" className="num">Solved</th>
                <th scope="col" className="num">A candidate was correct</th>
                <th scope="col" className="num">Model tokens</th>
                <th scope="col" className="num">Est. model cost</th>
                <th scope="col" className="num">Sandbox runs</th>
              </tr>
            </thead>
            <tbody>
              {MODES.map((m) => (
                <tr key={m} className={m === "branching" ? "is-lead" : undefined}>
                  <th scope="row">
                    {MODE_LABEL[m]}
                    <span className="row-note">{note[m]}</span>
                  </th>
                  <td className="num">
                    <strong>{totals[m].solved}</strong> / {index.tasks} <span className="dim">({pct(totals[m].solved)})</span>
                  </td>
                  <td className="num">{totals[m].any_candidate}</td>
                  <td className="num">{fmtTokens(totals[m].tokens)}</td>
                  <td className="num">{usd(totals[m].estimated_usd)}</td>
                  <td className="num">{totals[m].sandbox_runs.toLocaleString("en-US")}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="findings">
          <div>
            <p className="nameplate">Paired, same tasks</p>
            <p>
              Branching solved {cmp.branching_vs_matched.only_branching} tasks the matched attempts missed; they
              solved {cmp.branching_vs_matched.only_matched} that branching missed (exact McNemar p ={" "}
              {fmtP(cmp.branching_vs_matched.mcnemar_p)}). Against one attempt: {cmp.branching_vs_linear.only_branching}{" "}
              to {cmp.branching_vs_linear.only_linear} (p = {fmtP(cmp.branching_vs_linear.mcnemar_p)}).{" "}
              <strong>
                Against one attempt, branching's win is{" "}
                {significant(cmp.branching_vs_linear.mcnemar_p) ? "statistically significant" : "not statistically significant"}.
                At equal compute the direction is the same but{" "}
                {significant(cmp.branching_vs_matched.mcnemar_p) ? "also significant" : "not yet significant"} at{" "}
                {index.tasks} tasks.
              </strong>
            </p>
          </div>
          <div>
            <p className="nameplate">Read with care</p>
            <p>
              Absolute rates are low: a 3B-active model fails most of these bugs in every mode. "A candidate was
              correct" is an upper bound that counts patches the agent did not submit. Hidden tests were used only
              to grade, never shown to the agent or the judge.
            </p>
          </div>
          <div>
            <p className="nameplate">Cost</p>
            <p>
              Branching cost about {usd(perTask)} of model tokens per task, at Token Factory list prices; all
              three modes together about {usd(allModes)}. Estimates: reports keep input and output tokens per mode,
              not per model. Sandbox runs were not billed during the Sandboxes beta.
            </p>
          </div>
        </div>

        <ForkFindings index={index} onOpen={onOpen} />

        <div className="paired">
          <p className="nameplate">Every task any mode solved</p>
          <div className="table-scroll">
            <table className="paired-table">
              <thead>
                <tr>
                  <th scope="col">Task</th>
                  {MODES.map((m) => (
                    <th scope="col" key={m}>{MODE_LABEL[m]}</th>
                  ))}
                  <th scope="col"><span className="visually-hidden">Open</span></th>
                </tr>
              </thead>
              <tbody>
                {solvedRows.map((r) => (
                  <tr key={r.task}>
                    <th scope="row">
                      <span className="mono">{r.task}</span>
                    </th>
                    {MODES.map((m) => (
                      <td key={m}>
                        <Outcome solved={r.modes[m].solved} />
                      </td>
                    ))}
                    <td>
                      <button className="text-button" onClick={() => onOpen(r.task)}>
                        Replay<span className="visually-hidden"> {r.task}</span> →
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr>
                  <td colSpan={5}>The other {index.tasks - solvedRows.length} tasks: no mode solved them. All are in the replay below.</td>
                </tr>
              </tfoot>
            </table>
          </div>
        </div>
      </div>
    </section>
  );
}

function ForkFindings({ index, onOpen }: { index: RunIndex; onOpen: (task: string) => void }) {
  const f = index.forks;
  const needed = f.wins_needing_an_alternative;
  return (
    <div className="fork-findings">
      <p className="nameplate">Where the forks mattered</p>
      <p>
        Branching forked {f.forks} times across {f.tasks_with_forks} tasks, and at {f.divergent_forks} of those
        forks the sibling branches ended differently. At {f.decisive_forks}, one branch reached a passing patch
        and a sibling did not; at {f.decisive_where_own_action_failed} of these, the passing branch started from a
        sampled alternative rather than the agent's own next action.
      </p>
      <p>
        Following the agent's own action at every fork approximates what it would have done without forking. That
        path reached a passing patch in {f.wins_where_own_path_also_passed} of the {f.branching_wins} tasks
        branching solved. In the other {needed.length}, the fix came from an alternative:{" "}
        {needed.map((task, i) => (
          <span key={task}>
            <button className="text-button mono" onClick={() => onOpen(task)}>{shortTask(task)}</button>
            {i < needed.length - 1 ? ", " : "."}
          </span>
        ))}
      </p>
    </div>
  );
}

function usd(value: number | null | undefined): string {
  return value == null ? "n/a" : `$${value.toFixed(2)}`;
}

function fmtP(p: number): string {
  return p < 0.001 ? "< 0.001" : p.toFixed(3);
}

function significant(p: number): boolean {
  return p < 0.05;
}

function runDates(benchmark: RunIndex["benchmark"]): string {
  if ("sources" in benchmark) {
    const dates = [...new Set(benchmark.sources.map((s) => s.created))].sort();
    return dates.length > 1 ? `${dates[0]} to ${dates[dates.length - 1]}` : dates[0];
  }
  return benchmark.created;
}

function Outcome({ solved }: { solved: boolean }) {
  return solved ? <span className="outcome fix">✓ solved</span> : <span className="outcome">–</span>;
}

function Replay({ index, route, setRoute }: { index: RunIndex; route: Route; setRoute: (r: Route) => void }) {
  const [run, setRun] = useState<TaskRun | null>(null);
  const [upTo, setUpTo] = useState(30);
  const [playing, setPlaying] = useState(false);
  const cache = useRef(new Map<string, TaskRun>());

  useEffect(() => {
    let live = true;
    const hit = cache.current.get(route.task);
    const load = hit
      ? Promise.resolve(hit)
      : fetch(`/runs/${route.task}.json`, { cache: "no-cache" }).then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))));
    load
      .then((data: TaskRun) => {
        cache.current.set(route.task, data);
        if (live) setRun(data);
      })
      .catch(() => live && setRun(null));
    return () => {
      live = false;
    };
  }, [route.task]);

  const modeRun = run && run.task === route.task ? run.modes[route.mode] : null;
  const maxStep = modeRun?.config.max_steps ?? 30;

  useEffect(() => {
    setPlaying(false);
    setUpTo(maxStep);
  }, [route.task, route.mode, maxStep]);

  useEffect(() => {
    if (!playing) return;
    if (upTo >= maxStep) {
      setPlaying(false);
      return;
    }
    const t = window.setTimeout(() => setUpTo((s) => s + 1), 420);
    return () => window.clearTimeout(t);
  }, [playing, upTo, maxStep]);

  const selectedNode = modeRun ? (route.node && modeRun.nodes.some((n) => n.id === route.node) ? route.node : defaultNode(modeRun)) : null;

  const groups = useMemo(() => {
    const byRepo = new Map<string, IndexRow[]>();
    for (const r of [...index.rows].sort((a, b) => a.task.localeCompare(b.task, "en", { numeric: true }))) {
      byRepo.set(r.repo, [...(byRepo.get(r.repo) ?? []), r]);
    }
    return [...byRepo.entries()];
  }, [index.rows]);

  return (
    <section className="replay" id="replay" aria-labelledby="replay-title">
      <div className="wrap">
        <p className="nameplate">Run replay · all {index.tasks} tasks, all three modes</p>
        <h2 id="replay-title">Open any run and follow each branch to its verdict.</h2>

        <div className="replay-grid">
          <nav className="task-list" aria-label="Benchmark tasks">
            <label className="task-select">
              <span className="nameplate">Task</span>
              <select value={route.task} onChange={(e) => setRoute({ ...route, task: e.target.value, node: null })}>
                {groups.map(([repo, rows]) => (
                  <optgroup label={repo} key={repo}>
                    {rows.map((r) => (
                      <option key={r.task} value={r.task}>
                        {shortTask(r.task)}
                        {r.modes.branching.solved ? " · branching solved" : ""}
                      </option>
                    ))}
                  </optgroup>
                ))}
              </select>
            </label>
            <div className="task-groups">
              <p className="task-key nameplate" aria-hidden="true">
                <span>One · Matched · Branching</span>
              </p>
              {groups.map(([repo, rows]) => (
                <div key={repo} className="task-group">
                  <p className="nameplate">{repo}</p>
                  <ul>
                    {rows.map((r) => (
                      <li key={r.task}>
                        <button
                          className={`task-item${r.task === route.task ? " is-current" : ""}`}
                          aria-current={r.task === route.task ? "true" : undefined}
                          onClick={() => setRoute({ task: r.task, mode: route.mode, node: null })}
                        >
                          <span className="mono">{shortTask(r.task)}</span>
                          <span className="pips" aria-label={MODES.map((m) => `${MODE_LABEL[m]} ${r.modes[m].solved ? "solved" : "not solved"}`).join(", ")}>
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

          <div className="run">
            {!run || run.task !== route.task ? (
              <p className="dim">Loading {route.task}…</p>
            ) : (
              <>
                <div className="run-head">
                  <p className="nameplate">{run.repo}</p>
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
                        aria-selected={route.mode === m}
                        className="mode-tab"
                        onClick={() => setRoute({ ...route, mode: m, node: null })}
                      >
                        <span className="mode-name">{MODE_LABEL[m]}</span>
                        <span className={`mode-verdict${mr.solved ? " fix" : ""}`}>{mr.solved ? "✓ solved" : "not solved"}</span>
                        <span className="mode-cost mono">{fmtTokens(mr.tokens)} tokens · {mr.sandbox_runs} sandbox runs</span>
                      </button>
                    );
                  })}
                </div>

                {modeRun && selectedNode && (
                  <div role="tabpanel" className="mode-panel">
                    <div className="scrubber">
                      <button
                        className="ghost-button"
                        onClick={() => {
                          if (playing) return setPlaying(false);
                          if (upTo >= maxStep) setUpTo(0);
                          setPlaying(true);
                        }}
                      >
                        {playing ? "Pause" : upTo >= maxStep ? "Replay from step 0" : "Play"}
                      </button>
                      <label className="scrub">
                        <span className="nameplate">Step {upTo} of {maxStep}</span>
                        <input
                          type="range"
                          min={0}
                          max={maxStep}
                          value={upTo}
                          onChange={(e) => {
                            setPlaying(false);
                            setUpTo(Number(e.target.value));
                          }}
                        />
                      </label>
                    </div>

                    <div className="tree-scroll">
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
      <li>Agent steps run left to right.</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><line className="mark" x1="7" x2="7" y1="2" y2="12" /></svg> shell command</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><circle className="mark hollow" cx="7" cy="7" r="2.6" /></svg> read a file</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><rect className="mark solid" x="3.5" y="3.5" width="7" height="7" transform="rotate(45 7 7)" /></svg> edit or create a file</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><circle className="fork-dot" cx="7" cy="7" r="4.5" /></svg> fork: snapshot copied per alternative</li>
      <li><svg viewBox="0 0 14 14" aria-hidden="true"><line className="end-bar" x1="7" x2="7" y1="0" y2="14" /></svg> pruned by the judge</li>
      <li><span className="swatch fix" aria-hidden="true" /> route to a patch that passed the hidden tests</li>
    </ul>
  );
}

function Method() {
  return (
    <section className="method" aria-labelledby="method-title">
      <div className="wrap">
        <p className="nameplate">How it works</p>
        <h2 id="method-title">Snapshots make a failed attempt cheap to abandon.</h2>
        <ol className="method-steps">
          <li>
            <strong>Every action runs in a snapshot.</strong> A shell command starts a Sandbox instance from the
            current snapshot and returns a new one; reading a file starts nothing. States are immutable, so any
            earlier state can be resumed.
          </li>
          <li>
            <strong>Fork only where it matters.</strong> When the agent's next action would edit or create a file,
            two more candidate actions are sampled. Each distinct one continues in its own fork, with at most three
            fork points on any path from the start.
          </li>
          <li>
            <strong>Check, then prune.</strong> With more than four branches alive, each patch is run against the
            repository's existing tests (chosen from the files it changed) and scored by Nemotron 3 Super. Branches
            that break existing tests rank last.
          </li>
          <li>
            <strong>Submit one patch.</strong> The selected patch prefers no regressions, then an explicit submit,
            then the judge's score. Only then is it graded with the task's hidden tests.
          </li>
        </ol>
        <p className="method-note">
          Tasks come from SWE-bench Lite. Of 104 held-out pytest-based tasks, all 79 that grade correctly in this
          harness are covered here: the first 40, drawn with a fixed seed proportionally by repository, then the
          remaining 39. django and sympy use other test runners and are out of scope.
        </p>
      </div>
    </section>
  );
}
