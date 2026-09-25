import { nodeName } from "./TreeView";
import { fmtScore, lineage, stopWords } from "./tree";
import type { Candidate, ModeName, ModeRun } from "./types";

interface Props {
  mode: ModeName;
  run: ModeRun;
  nodeId: string;
}

export default function BranchDetail({ mode, run, nodeId }: Props) {
  const path = lineage(run, nodeId);
  const node = path[path.length - 1]?.node;
  if (!node) return null;
  const cand = run.candidates[node.id];
  const submitted = run.selected === node.id;
  const name = nodeName(mode, node.id);

  return (
    <article className="detail" aria-labelledby="detail-title">
      <header className="detail-head">
        <div>
          <p className="nameplate">{node.stop === "branched" ? "Fork point" : "Viewing"}</p>
          <h4 id="detail-title">
            {name}
            <span className={`detail-verdict${cand?.resolved ? " fix" : ""}`}>
              {stopWords(node, cand ? cand.resolved : null)}
            </span>
          </h4>
        </div>
        {submitted && <p className="submitted-tag">Submitted by Forkfix</p>}
      </header>

      {node.stop === "branched" && (
        <p className="detail-note">
          At step {node.end} this trajectory was about to change code, so its snapshot was forked. Select a branch
          to the right of the fork to follow it.
        </p>
      )}
      {node.stop === "pruned" && (
        <p className="detail-note">
          More than {run.config.width} branches were alive, and this one ranked below the rest
          {node.score !== null ? ` (judge ${fmtScore(node.score)})` : ""}. Its snapshot was dropped.
        </p>
      )}

      {cand && <Verdict cand={cand} />}

      <div className="steps">
        <p className="nameplate">Every step on this path</p>
        <ol>
          {path.map(({ node: n, events }, i) => (
            <li key={n.id} className="step-group">
              {mode === "branching" && (
                <p className="step-group-head">
                  {i === 0 ? `Branch ${n.id}` : `Forked at step ${n.born} → branch ${n.id}`}
                  {n.id !== node.id && <span className="dim"> · shared with its sibling branches</span>}
                </p>
              )}
              <ol className="events">
                {events.map((e) => (
                  <li key={e.step}>
                    <details className={`event tool-${e.tool}`}>
                      <summary>
                        <span className="event-step mono">{String(e.step).padStart(2, "0")}</span>
                        <span className="event-tool nameplate">{e.tool}</span>
                        <span className="event-summary mono">{e.summary.replace(/^\w+: ?/, "")}</span>
                      </summary>
                      <div className="event-body">
                        <pre>{e.observation || "(no output)"}</pre>
                        <p className="dim mono">snapshot {e.snapshot || "n/a"} · output trimmed to 400 characters</p>
                      </div>
                    </details>
                  </li>
                ))}
              </ol>
            </li>
          ))}
        </ol>
      </div>
    </article>
  );
}

function Verdict({ cand }: { cand: Candidate }) {
  const [f2p, f2pTotal] = cand.fail_to_pass;
  const [p2p, p2pTotal] = cand.pass_to_pass;
  return (
    <div className="verdict">
      <dl>
        <div className={cand.resolved ? "fix" : undefined}>
          <dt className="nameplate">Hidden tests (grading only)</dt>
          <dd>
            <strong>{cand.resolved ? "✓ Passed" : "✗ Failed"}</strong>
            <span className="mono dim">
              {" "}
              {f2p ?? "?"}/{f2pTotal ?? "?"} failing tests now pass · {p2p ?? "?"}/{p2pTotal ?? "?"} passing tests still pass
            </span>
          </dd>
        </div>
        <div>
          <dt className="nameplate">Judge, Nemotron 3 Super</dt>
          <dd>{cand.judge === null ? "not scored" : fmtScore(cand.judge)}</dd>
        </div>
        <div>
          <dt className="nameplate">Existing tests, seen before selection</dt>
          <dd>{cand.broken ? "Broken. " : ""}{cand.existing_tests ?? "none found for the changed files"}</dd>
        </div>
      </dl>
      <details className="patch" open>
        <summary className="nameplate">Patch</summary>
        <pre className="diff">
          {cand.patch.split("\n").map((line, i) => (
            <span
              key={i}
              className={line.startsWith("+") && !line.startsWith("+++") ? "add" : line.startsWith("-") && !line.startsWith("---") ? "del" : line.startsWith("@@") ? "hunk" : undefined}
            >
              {line}
              {"\n"}
            </span>
          ))}
        </pre>
      </details>
    </div>
  );
}
