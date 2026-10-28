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
  const [showAttempts, setShowAttempts] = useState(false);

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
      title="Does it work outside the benchmark?"
      lede="We also pointed it at real, open issues on public projects, where there is no answer key. It writes its own test first, then works until that test passes."
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
        <>
          <dl className="num grid max-w-[760px] grid-cols-2 gap-x-8 gap-y-5 sm:grid-cols-4">
            {[
              [data.issues, "open issues tried"],
              [data.patched, "got a patch"],
              [data.proven, "passed the agent's own test"],
              [data.clean, "passed it without breaking anything"],
            ].map(([n, l]) => (
              <div key={l}>
                <dd className="text-3xl font-semibold leading-none tracking-[-0.03em]">{n}</dd>
                <dt className="mt-1.5 text-sm text-muted">{l}</dt>
              </div>
            ))}
          </dl>
          <p className="mt-4 max-w-[62ch] text-sm text-muted">
            Honest caveat: when we checked the confirmed fixes by hand, some had flaws. Open an issue below to see what we found.
          </p>

          <div className="mt-8 grid gap-8 lg:grid-cols-[360px_minmax(0,1fr)]">
            <ul className="max-h-72 self-start overflow-y-auto border-y border-rule lg:max-h-[26rem]">
              {data.rows.map((r) => {
                const on = r.issue === issue.issue;
                return (
                  <li key={r.issue} className="border-b border-rule last:border-b-0">
                    <button
                      type="button"
                      aria-current={on ? "true" : undefined}
                      onClick={() => {
                        setSel(r.issue);
                        setShowAttempts(false);
                      }}
                      className={`block min-h-11 w-full px-3 py-2.5 text-left text-sm transition-colors ${on ? "bg-accent-tint" : "hover:bg-panel"}`}
                    >
                      <span className="line-clamp-2 block font-medium">{r.title}</span>
                      <span className={`mt-0.5 block text-sm ${r.proven ? "text-ink" : "text-muted"}`}>{verdict(r)}</span>
                    </button>
                  </li>
                );
              })}
            </ul>

            <div className="min-w-0">
              <h3 className="max-w-[44ch] text-xl font-semibold leading-snug tracking-tight">{issue.title}</h3>
              <p className="mt-2 text-sm text-muted">
                {issue.issue} ·{" "}
                <a className="inline-flex min-h-9 items-center underline underline-offset-4 hover:text-accent" href={issue.url}>
                  Open on GitHub
                </a>
              </p>
              <p className="mt-3">
                <span className={`rounded-sm px-2 py-0.5 text-sm font-medium ${issue.proven ? "bg-ink text-paper" : "border border-rule-strong"}`}>{verdict(issue)}</span>{" "}
                <span className="num text-sm text-muted">{fmtTokens(issue.tokens)} tokens of AI work</span>
              </p>
              {issue.review ? (
                <p className="mt-5 max-w-[62ch] rounded-md bg-panel p-4 text-[15px]">
                  <span className="font-medium">Checked by hand: </span>
                  {issue.review}
                </p>
              ) : null}
              {issue.note ? (
                <details className="mt-3 max-w-[62ch]">
                  <summary className="inline-flex min-h-9 cursor-pointer items-center text-sm underline underline-offset-4 hover:text-accent">Technical notes</summary>
                  <p className="mt-1 text-[15px] text-muted">{issue.note}</p>
                </details>
              ) : null}

              {issue.candidates.length ? (
                <div className="mt-5">
                  <button
                    type="button"
                    aria-expanded={showAttempts}
                    onClick={() => setShowAttempts((v) => !v)}
                    className="inline-flex min-h-11 items-center text-sm underline underline-offset-4 hover:text-accent"
                  >
                    {showAttempts ? "Hide the attempts" : `See the ${issue.candidates.length} attempts`}
                  </button>
                  {showAttempts ? (
                    <ul className="mt-2 divide-y divide-rule border-y border-rule">
                      {issue.candidates.map((c, i) => (
                        <li key={c.id} className="grid gap-x-6 gap-y-1 py-3 text-sm sm:grid-cols-[auto_minmax(0,1fr)]">
                          <p className="font-medium">
                            Attempt {i + 1}
                            {c.id === issue.selected ? <span className="ml-2 text-accent">chosen</span> : null}
                          </p>
                          <p className="text-muted">
                            {c.steps} steps · {c.proven ? "its own test passes" : "its own test still fails"}
                            {c.regressions ? ", but it breaks an existing test" : ""}
                          </p>
                        </li>
                      ))}
                    </ul>
                  ) : null}
                </div>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </Section>
  );
}
