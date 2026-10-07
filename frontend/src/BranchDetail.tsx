import { useEffect, useState } from "react";

import { nodeName } from "./TreeView";
import { fmtScore, lineage, stopWords } from "./tree";
import type { Candidate, ModeName, ModeRun } from "./types";

interface Props {
  mode: ModeName;
  run: ModeRun;
  nodeId: string;
}

type Tab = "verdict" | "patch" | "steps";

export default function BranchDetail({ mode, run, nodeId }: Props) {
  const path = lineage(run, nodeId);
  const node = path[path.length - 1]?.node;
  const cand = node ? run.candidates[node.id] : undefined;
  const [tab, setTab] = useState<Tab>("verdict");

  // A fork or a pruned branch has no graded patch; fall back to the steps that led there.
  useEffect(() => {
    setTab(cand ? "verdict" : "steps");
  }, [nodeId, cand]);

  if (!node) return null;
  const submitted = run.selected === node.id;
  const name = nodeName(mode, node.id);
  const stepCount = path.reduce((n, p) => n + p.events.length, 0);
  const tabs: { id: Tab; label: string; hint?: string }[] = [
    ...(cand ? ([{ id: "verdict", label: "Verdict" }, { id: "patch", label: "Patch" }] as const) : []),
    { id: "steps", label: "Steps", hint: String(stepCount) },
  ];

  return (
    <article className="detail" aria-labelledby="detail-title">
      <header className="detail-head">
        <div>
          <p className="stamp">{node.stop === "branched" ? "Fork point" : "Selected"}</p>
          <h4 id="detail-title">
            {name}
            <span className={`detail-verdict${cand?.resolved ? " fix" : ""}`}>{stopWords(node, cand ? cand.resolved : null)}</span>
          </h4>
        </div>
        {submitted && <p className="tag tag-solid">Submitted by Forkfix</p>}
      </header>

      {node.stop === "branched" && (
        <p className="detail-note">
          At step {node.end} this trajectory was about to change code, so its snapshot was forked. Select a branch to the
          right of the fork to follow it.
        </p>
      )}
      {node.stop === "pruned" && (
        <p className="detail-note">
          More than {run.config.width} branches were alive, and this one ranked below the rest
          {node.score !== null ? ` (judge ${fmtScore(node.score)})` : ""}. Its snapshot was dropped.
        </p>
      )}

      <div className="tabs" role="tablist" aria-label="Branch detail">
        {tabs.map((t) => (
          <button
            key={t.id}
            role="tab"
            id={`tab-${t.id}`}
            aria-selected={tab === t.id}
            aria-controls={`panel-${t.id}`}
            tabIndex={tab === t.id ? 0 : -1}
            className="tab"
            onClick={() => setTab(t.id)}
            onKeyDown={(e) => {
              const i = tabs.findIndex((x) => x.id === tab);
              const next = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : null;
              if (next === null) return;
              e.preventDefault();
              const target = tabs[(next + tabs.length) % tabs.length].id;
              setTab(target);
              document.getElementById(`tab-${target}`)?.focus();
            }}
          >
            {t.label}
            {t.hint && <span className="tab-hint mono">{t.hint}</span>}
          </button>
        ))}
      </div>

      <div role="tabpanel" id={`panel-${tab}`} aria-labelledby={`tab-${tab}`} className="tab-panel">
        {tab === "verdict" && cand && <Verdict cand={cand} />}
        {tab === "patch" && cand && <Patch cand={cand} />}
        {tab === "steps" && (
          <ol className="step-groups">
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
                          <span className="event-tool stamp">{e.tool}</span>
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
        )}
      </div>
    </article>
  );
}

function Verdict({ cand }: { cand: Candidate }) {
  const [f2p, f2pTotal] = cand.fail_to_pass;
  const [p2p, p2pTotal] = cand.pass_to_pass;
  return (
    <dl className="verdict-grid">
      <div className={cand.resolved ? "is-pass" : undefined}>
        <dt className="stamp">Hidden tests · grading only</dt>
        <dd>
          <strong>{cand.resolved ? "✓ Passed" : "✗ Failed"}</strong>
          <span className="mono dim">
            {f2p ?? "?"}/{f2pTotal ?? "?"} failing tests now pass · {p2p ?? "?"}/{p2pTotal ?? "?"} passing tests still pass
          </span>
        </dd>
      </div>
      <div>
        <dt className="stamp">Judge · Nemotron 3 Super</dt>
        <dd>
          <strong>{cand.judge === null ? "not scored" : fmtScore(cand.judge)}</strong>
        </dd>
      </div>
      <div>
        <dt className="stamp">Existing tests · seen before selection</dt>
        <dd>
          <strong>{cand.broken ? "Broken" : "No break"}</strong>
          <span className="mono dim">{cand.existing_tests ?? "none found for the changed files"}</span>
        </dd>
      </div>
    </dl>
  );
}

function Patch({ cand }: { cand: Candidate }) {
  if (!cand.patch.trim()) return <p className="empty">This branch ended without a patch.</p>;
  return (
    <pre className="diff" tabIndex={0} aria-label="Patch">
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
  );
}
