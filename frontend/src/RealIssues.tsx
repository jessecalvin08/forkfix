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
      ? `On ${data.issues} real GitHub issues, ${data.clean} fix${data.clean === 1 ? " was" : "es were"} proven and held up on review.`
      : data.proven > 0
        ? `On ${data.issues} real GitHub issues, ${data.proven} patch${data.proven === 1 ? "" : "es"} passed ${data.proven === 1 ? "its" : "their"} own proof check; none held up on review.`
        : `On ${data.issues} real GitHub issues, no patch passed the proof check.`;
  const rerun = sorted.filter((r) => r.run >= AGENT_CHANGED_ON).length;

  return (
    <section className="section real" id="real-issues" aria-labelledby="real-title">
      <div className="wrap">
        <header className="section-head">
          <p className="stamp">Real issues · first live run · {fmtRunDate(sorted[0].run)}</p>
          <h2 id="real-title">{heading}</h2>
        </header>

        <div className="real-lead">
          <p>
            Real issues have no hidden tests, so Forkfix makes the agent write its own reproduction test first. A branch
            counts as a fix only if that test <strong>fails on the unfixed repository and passes on the branch</strong>,
            and the project's existing tests still pass. The judge's score is not proof, and neither is the agent's own
            test: {data.clean > 0
              ? `most patches that passed it either broke a test the project already had or failed on inputs the agent's test never tried; ${data.clean} held up under a hand-written check.`
              : "the patches that passed it either broke a test the project already had or failed on inputs the agent's test never tried."}
          </p>
          <ol className="funnel real-funnel" aria-label="Real-issue outcomes">
            <li><strong>{data.issues}</strong><span>issues run</span></li>
            <li><strong>{data.patched}</strong><span>produced any patch</span></li>
            <li><strong>{data.proven}</strong><span>passed their own proof test</span></li>
            <li><strong>{data.clean}</strong><span>held up on review</span></li>
          </ol>
        </div>
        <p className="fine real-meta">
          {fmtTokens(data.tokens)} model tokens in total. {rerun > 0
            ? `${rerun} of the ${data.issues} runs used the agent after it was changed (no package installs, more steps, a cap on unproven scores, a fallback that runs a small test suite whole); the other ${data.issues - rerun} ${data.issues - rerun === 1 ? "is" : "are"} from before those changes.`
            : "The agent has been changed since these runs (no package installs, more steps, a cap on unproven scores); those changes have not been run against a live model."}
        </p>

        <div className="table-scroll" role="region" aria-label="Real issues, scrollable" tabIndex={0}>
          <table className="real-table">
            <thead>
              <tr>
                <th scope="col">Issue</th>
                <th scope="col" className="num">Patches</th>
                <th scope="col" className="num">Best judge</th>
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
        <p className="fine real-foot">
          The first six issues were chosen by a person from open, unassigned bugs with no competing pull request. The
          later ones (dateutil, arrow, sqlparse) were chosen as clear bugs with exact examples, and each already has an open
          pull request from someone else, so they are test cases only. Nothing has been submitted to any project.
        </p>
      </div>
    </section>
  );
}

const fmtRunDate = (run: string): string => (/^\d{8}$/.test(run) ? `${run.slice(0, 4)}-${run.slice(4, 6)}-${run.slice(6)}` : run);

function bestJudge(row: RealIssue): number | null {
  const scores = row.candidates.map((c) => c.judge).filter((s): s is number => s != null);
  return scores.length ? Math.max(...scores) : null;
}

function proofLabel(row: RealIssue): string {
  if (row.candidates.length === 0) return "No patch";
  const proven = row.candidates.filter((c) => c.proven).length;
  if (proven === 0) return `Not proven (0 of ${row.candidates.length})`;
  const breaking = row.candidates.filter((c) => c.proven && c.regressions).length;
  if (breaking === proven) return `Passed its own test, breaks an existing test (${proven} of ${row.candidates.length})`;
  if (row.review) return `Passed its own test, failed review (${proven} of ${row.candidates.length})`;
  return `Proven (${proven} of ${row.candidates.length})`;
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
          <span className={`proof${row.clean ? " proven" : ""}`}>{proofLabel(row)}</span>
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
                No branch finished with a change to the project's source. Branches ran out of their {row.max_steps}-step
                budget or were pruned.
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
