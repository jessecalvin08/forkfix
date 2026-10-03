import { useEffect, useMemo, useState } from "react";

import { fmtTokens } from "./tree";
import type { IssueCandidate, RealIssue, RealIssueIndex } from "./types";

/**
 * The first live run on real GitHub issues. No hidden tests exist for these, so a fix counts only
 * when the agent's own reproduction test fails on the unfixed repository and passes on the branch.
 * Nothing here is green: green is reserved for patches that passed.
 */
/** Runs dated on or after this used the agent changes made after the first live run. */
const AGENT_CHANGED_ON = "20261001";

export default function RealIssues() {
  const [data, setData] = useState<RealIssueIndex | null>(null);

  useEffect(() => {
    fetch("/fix/index.json", { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then(setData)
      .catch(() => setData(null));
  }, []);

  if (!data || data.rows.length === 0) return null;

  const sorted = [...data.rows].sort((a, b) => a.issue.localeCompare(b.issue, "en", { numeric: true }));
  const heading =
    data.clean > 0
      ? `On ${data.issues} real GitHub issues, ${data.clean} fix${data.clean === 1 ? " was" : "es were"} proven and breaks no existing test.`
      : data.proven > 0
        ? `On ${data.issues} real GitHub issues, ${data.proven} patch passed its own proof check, and it breaks an existing test.`
        : `On ${data.issues} real GitHub issues, no patch passed the proof check.`;
  const rerun = sorted.filter((r) => r.run >= AGENT_CHANGED_ON).length;

  return (
    <section className="real" id="real-issues" aria-labelledby="real-title">
      <div className="wrap">
        <p className="nameplate">Real issues · first live run · {sorted[0].run}</p>
        <h2 id="real-title">{heading}</h2>

        <div className="real-intro">
          <p>
            Real issues have no hidden tests to grade against, so Forkfix asks the agent to write its own reproduction
            test first. A branch counts as a fix only if that test <strong>fails on the unfixed repository and passes
            on the branch</strong>, and it should not break the project's existing tests. The judge model scores
            patches too, but its score alone is not proof, and neither is the agent's own test: the one patch that
            passed it breaks a test the project already had.
          </p>
          <p>
            {data.patched} of {data.issues} runs produced any patch. Together they used {fmtTokens(data.tokens)} model
            tokens. {rerun > 0
              ? `${rerun} issue${rerun === 1 ? " was" : "s were"} re-run after the agent was changed (no package installs, more steps, a cap on unproven scores); the other ${data.issues - rerun} are from before those changes and have not been re-run.`
              : "The agent has been changed since these runs (no package installs, more steps, a cap on unproven scores); those changes have not been run against a live model."}
          </p>
        </div>

        <div className="table-scroll">
          <table className="real-table">
            <thead>
              <tr>
                <th scope="col">Issue</th>
                <th scope="col" className="num">Patches</th>
                <th scope="col" className="num">Best judge score</th>
                <th scope="col">Proof check</th>
                <th scope="col" className="num">Tokens</th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <IssueRow key={row.issue} row={row} />
              ))}
            </tbody>
          </table>
        </div>
        <p className="real-foot">
          Issues were chosen by a person from open, unassigned bugs with no competing pull request; nothing has been
          submitted to any project.
        </p>
      </div>
    </section>
  );
}

function bestJudge(row: RealIssue): number | null {
  const scores = row.candidates.map((c) => c.judge).filter((s): s is number => s != null);
  return scores.length ? Math.max(...scores) : null;
}

function proofLabel(row: RealIssue): string {
  if (row.candidates.length === 0) return "No patch";
  const proven = row.candidates.filter((c) => c.proven).length;
  if (proven === 0) return `Not proven (0 of ${row.candidates.length})`;
  const breaking = row.candidates.filter((c) => c.proven && c.regressions).length;
  return breaking === proven
    ? `Passed its own test, breaks an existing test (${proven} of ${row.candidates.length})`
    : `Proven (${proven} of ${row.candidates.length})`;
}

function IssueRow({ row }: { row: RealIssue }) {
  const best = bestJudge(row);
  return (
    <>
      <tr>
        <th scope="row">
          <a className="mono" href={row.url}>{row.issue}</a>
          <span className="row-note">{row.title}</span>
        </th>
        <td className="num">{row.candidates.length}</td>
        <td className="num">{best == null ? "–" : `${best} / 10`}</td>
        <td>
          <span className={`verdict${row.clean ? " proven" : ""}`}>{proofLabel(row)}</span>
        </td>
        <td className="num">{fmtTokens(row.tokens)}</td>
      </tr>
      <tr className="detail-row">
        <td colSpan={5}>
          <details className="issue-detail">
            <summary>What happened on {row.issue}</summary>
            {row.note && <p className="issue-note">{row.note}</p>}
            {row.candidates.length === 0 ? (
              <p className="dim">
                No branch finished with a change to the project's source. The agent used its {row.max_steps}-step
                budget reading a large file.
              </p>
            ) : (
              <ul className="cand-list">
                {row.candidates.map((c) => (
                  <Candidate key={c.id} c={c} selected={c.id === row.selected} issue={row.issue} />
                ))}
              </ul>
            )}
          </details>
        </td>
      </tr>
    </>
  );
}

function patchHref(patch: string): string {
  const text = patch.endsWith("\n") ? patch : `${patch}\n`;
  return URL.createObjectURL(new Blob([text], { type: "text/x-diff" }));
}

function Candidate({ c, selected, issue }: { c: IssueCandidate; selected: boolean; issue: string }) {
  const href = useMemo(() => (c.patch ? patchHref(c.patch) : null), [c.patch]);
  useEffect(() => () => { if (href) URL.revokeObjectURL(href); }, [href]);
  return (
    <li className="cand">
      <p className="cand-head">
        <span className="mono">branch {c.id}</span>
        {selected && <span className="tag">selected</span>}
        <span className="dim">
          {c.steps} steps · ended: {c.stop.replace("_", " ")} · judge {c.judge ?? "–"} / 10
        </span>
      </p>
      <p className="cand-line"><strong>Proof:</strong> {c.reproduction ?? "not run"}</p>
      <p className="cand-line"><strong>Existing tests:</strong> {c.existing_tests || "not run"}</p>
      {c.patch && (
        <details>
          <summary>Patch</summary>
          <p>
            <a className="mono" href={href ?? undefined} download={`${issue.replace(/[^\w.-]+/g, "-")}-branch-${c.id}.patch`}>
              Download .patch
            </a>
            <span className="dim"> · review before applying; not a proven fix unless marked so above</span>
          </p>
          <pre>{c.patch}</pre>
        </details>
      )}
    </li>
  );
}
