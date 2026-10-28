import { useEffect, useState } from "react";

import { Section } from "@/components/chrome";
import { fmtTokens, getJSON, type RealIssue, type RealIssueIndex } from "@/data";

const verdict = (r: RealIssue) =>
  r.clean ? "Fix confirmed, nothing else broke" : r.proven ? "Fix confirmed by its own test" : r.candidates.length ? "Patch written, not confirmed" : "No patch";

export function RealIssues() {
  const [data, setData] = useState<RealIssueIndex | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [sel, setSel] = useState<string | null>(null);

  useEffect(() => {
    setFailed(false);
    getJSON<RealIssueIndex>("/fix/index.json")
      .then(setData)
      .catch(() => setFailed(true));
  }, [retry]);

  const issue = data?.rows.find((r) => r.issue === (sel ?? data.rows[0]?.issue));

  return (
    <Section
      id="real-issues-title"
      anchor="real-issues"
      stack
      title="The same idea on open GitHub issues"
      lede={
        data
          ? `These are real, open issues on public projects, so there is no answer key. The agent first writes its own small test that fails because of the bug, then keeps working until that test passes. Of ${data.issues} issues, ${data.patched} got a patch, ${data.proven} were confirmed by the agent's own test, and ${data.clean} were confirmed without breaking any existing test.`
          : "These are real, open issues on public projects, so there is no answer key."
      }
    >
      {failed ? (
        <p role="alert" className="text-muted">
          The real-issue results did not load.{" "}
          <button type="button" className="underline underline-offset-4 hover:text-accent" onClick={() => setRetry((n) => n + 1)}>
            Try again
          </button>
        </p>
      ) : null}

      {data && issue ? (
        <div className="grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)]">
          <ul className="self-start border-y border-rule">
            {data.rows.map((r) => {
              const on = r.issue === issue.issue;
              return (
                <li key={r.issue} className="border-b border-rule last:border-b-0">
                  <button
                    type="button"
                    aria-current={on ? "true" : undefined}
                    onClick={() => setSel(r.issue)}
                    className={`block min-h-11 w-full px-3 py-2.5 text-left text-sm transition-colors ${on ? "bg-accent-tint" : "hover:bg-panel"}`}
                  >
                    <span className="block truncate font-mono text-[13px] font-medium">{r.issue}</span>
                    <span className={`block text-sm ${r.proven ? "text-ink" : "text-muted"}`}>{verdict(r)}</span>
                  </button>
                </li>
              );
            })}
          </ul>

          <div className="min-w-0">
            <h3 className="max-w-[44ch] text-xl font-semibold leading-snug tracking-tight">{issue.title}</h3>
            <p className="num mt-3 flex flex-wrap items-center gap-x-4 gap-y-1 font-mono text-sm text-muted">
              <span className={`rounded-sm px-2 py-0.5 font-sans font-medium ${issue.proven ? "bg-ink text-paper" : "border border-rule-strong text-ink"}`}>
                {verdict(issue)}
              </span>
                            <span>{fmtTokens(issue.tokens)} tokens of AI work</span>
              <a className="inline-flex min-h-9 items-center font-sans text-ink underline underline-offset-4 hover:text-accent" href={issue.url}>
                Open on GitHub
              </a>
            </p>
            {issue.review ? (
              <p className="mt-6 max-w-[70ch] rounded-md bg-panel p-4 text-[15px]">
                <span className="font-medium">Checked by hand: </span>
                {issue.review}
              </p>
            ) : null}
            {issue.note ? <p className="mt-4 max-w-[70ch] text-[15px] text-muted">{issue.note}</p> : null}

            <h4 className="mb-3 mt-8 font-semibold">Attempts</h4>
            <ul className="divide-y divide-rule border-y border-rule">
              {issue.candidates.map((c) => (
                <li key={c.id} className="grid gap-x-6 gap-y-1 py-3 text-sm sm:grid-cols-[auto_minmax(0,1fr)]">
                  <p className="font-mono">
                    <span className="font-medium">Attempt {issue.candidates.indexOf(c) + 1}</span>
                    {c.id === issue.selected ? <span className="ml-2 font-sans font-medium text-accent">selected</span> : null}
                  </p>
                  <p className="text-muted">
                    {c.steps} steps · {c.proven ? "its own test passes" : "its own test still fails"}
                    {c.regressions ? ", but it breaks an existing test" : ""}
                  </p>
                </li>
              ))}
            </ul>
          </div>
        </div>
      ) : null}
    </Section>
  );
}
