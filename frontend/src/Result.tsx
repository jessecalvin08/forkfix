import { fmtTokens, shortTask } from "./tree";
import { fmtP, significant, usd } from "./shared";
import { MODES, MODE_LABEL, type ModeName, type RunIndex } from "./types";

const NOTE: Record<ModeName, string> = {
  linear: "One trajectory, temperature 0.",
  matched: "Independent attempts, four at a time, given the tokens branching spent on the same task.",
  branching: "Forks at code changes. At most three fork points on a path, four branches alive.",
};

export default function Result({ index, onOpen }: { index: RunIndex; onOpen: (task: string) => void }) {
  const { totals, comparisons: cmp, forks: f } = index;
  const branchingUsd = totals.branching.estimated_usd;
  const perTask = branchingUsd == null ? null : branchingUsd / index.tasks;
  const needed = f.wins_needing_an_alternative;
  const allModes = MODES.some((m) => totals[m].estimated_usd == null)
    ? null
    : MODES.reduce((sum, m) => sum + (totals[m].estimated_usd ?? 0), 0);

  return (
    <section className="section result" id="result" aria-labelledby="result-title">
      <div className="wrap">
        <header className="section-head">
          <p className="stamp">Benchmark · {index.tasks} held-out tasks · {runDates(index.benchmark)}</p>
          <h2 id="result-title">
            Branching fixed {totals.branching.solved} of {index.tasks}. Independent attempts with the same tokens fixed{" "}
            {totals.matched.solved}.
          </h2>
        </header>

        {/* Ledger: bar length is the solved count; the open end is how many tasks produced a correct candidate. */}
        <div className="table-scroll" role="region" aria-label="Results by mode, scrollable" tabIndex={0}>
          <table className="ledger">
            <thead>
              <tr>
                <th scope="col">Mode, all Nemotron 3 Nano</th>
                <th scope="col" className="bar-col">
                  Tasks solved of {index.tasks}
                </th>
                <th scope="col" className="num">A candidate was right</th>
                <th scope="col" className="num">Tokens</th>
                <th scope="col" className="num">Est. cost</th>
                <th scope="col" className="num">Sandbox runs</th>
              </tr>
            </thead>
            <tbody>
              {[...MODES].reverse().map((m) => {
                const t = totals[m];
                return (
                  <tr key={m} className={m === "branching" ? "is-lead" : undefined}>
                    <th scope="row">
                      {MODE_LABEL[m]}
                      <span className="row-note">{NOTE[m]}</span>
                    </th>
                    <td className="bar-col">
                      <div className="bar" aria-hidden="true">
                        <span className="bar-solved" style={{ width: `${(100 * t.solved) / index.tasks}%` }} />
                        <span
                          className="bar-cand"
                          style={{ left: `${(100 * t.solved) / index.tasks}%`, width: `${(100 * (t.any_candidate - t.solved)) / index.tasks}%` }}
                        />
                      </div>
                      <span className="bar-n">
                        <strong>{t.solved}</strong>
                        <span className="dim"> · {pct(t.solved, index.tasks)}</span>
                      </span>
                    </td>
                    <td className="num">{t.any_candidate}</td>
                    <td className="num">{fmtTokens(t.tokens)}</td>
                    <td className="num">{usd(t.estimated_usd)}</td>
                    <td className="num">{t.sandbox_runs.toLocaleString("en-US")}</td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="key-line">
          <span className="key-swatch k-solved" aria-hidden="true" /> solved: the submitted patch passed the hidden tests
          <span className="key-swatch k-open" aria-hidden="true" /> a candidate passed, but it was not the one submitted
        </p>

        <div className="split">
          <div className="paired">
            <p className="stamp">Paired on the same tasks</p>
            <Pair label="Branching vs one attempt" won={cmp.branching_vs_linear.only_branching} lost={cmp.branching_vs_linear.only_linear} p={cmp.branching_vs_linear.mcnemar_p} />
            <Pair label="Branching vs equal-token attempts" won={cmp.branching_vs_matched.only_branching} lost={cmp.branching_vs_matched.only_matched} p={cmp.branching_vs_matched.mcnemar_p} />
            <p className="fine">
              Won and lost count tasks only one side solved; exact McNemar test. At equal compute the direction
              matches, but {index.tasks} tasks are not enough to call it.
            </p>
          </div>

          <div className="notes">
            <div>
              <p className="stamp">Read with care</p>
              <p>
                Absolute rates are low: a 3B-active model fails most of these bugs in every mode. “A candidate was
                right” is an upper bound that counts patches the agent did not submit. Hidden tests grade; they were
                never shown to the agent or the judge.
              </p>
            </div>
            <div>
              <p className="stamp">Cost</p>
              <p>
                About {usd(perTask)} of model tokens per task for branching, {usd(allModes)} for all three modes, at
                Token Factory list prices. Estimates: reports keep tokens per mode, not per model. Sandbox runs were
                not billed during the Sandboxes beta.
              </p>
            </div>
          </div>
        </div>

        <div className="forks">
          <p className="stamp">Where the forks mattered</p>
          <ol className="funnel" aria-label="Fork outcomes">
            <li><strong>{f.forks}</strong><span>forks across {f.tasks_with_forks} tasks</span></li>
            <li><strong>{f.divergent_forks}</strong><span>ended with siblings that differed</span></li>
            <li><strong>{f.decisive_forks}</strong><span>one sibling passed, another did not</span></li>
            <li><strong>{f.decisive_where_own_action_failed}</strong><span>of those, the agent’s own next action was the one that failed</span></li>
          </ol>
          <p className="forks-prose">
            Following the agent’s own action at every fork approximates a run without forking. That path also reached
            a passing patch in {f.wins_where_own_path_also_passed} of the {f.branching_wins} tasks branching solved. The
            other {needed.length} needed a sampled alternative:
          </p>
          <ul className="chips" aria-label="Tasks that needed an alternative">
            {needed.map((task) => (
              <li key={task}>
                <button className="chip" onClick={() => onOpen(task)}>
                  {shortTask(task)}
                </button>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </section>
  );
}

function Pair({ label, won, lost, p }: { label: string; won: number; lost: number; p: number }) {
  const total = won + lost || 1;
  return (
    <div className="pair">
      <div className="pair-head">
        <span>{label}</span>
        <span className="mono dim">p = {fmtP(p)}</span>
      </div>
      <div className="split-bar" role="img" aria-label={`${won} tasks only branching solved, ${lost} only the other mode solved`}>
        <span className="won" style={{ flexGrow: won }} />
        <span className="lost" style={{ flexGrow: lost }} />
      </div>
      <div className="pair-foot mono">
        <span>{won} won</span>
        <span>{significant(p) ? "significant" : "not significant"}</span>
        <span>{lost} lost</span>
      </div>
      <span className="visually-hidden">{Math.round((100 * won) / total)}% of the decided tasks went to branching.</span>
    </div>
  );
}

const pct = (n: number, of: number): string => {
  const v = (100 * n) / of;
  return `${Number.isInteger(v) ? v : v.toFixed(1)}%`;
};

function runDates(benchmark: RunIndex["benchmark"]): string {
  if ("sources" in benchmark) {
    const dates = [...new Set(benchmark.sources.map((s) => s.created))].sort();
    return dates.length > 1 ? `run ${dates[0]} to ${dates[dates.length - 1]}` : `run ${dates[0]}`;
  }
  return `run ${benchmark.created}`;
}
