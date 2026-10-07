const STEPS: { title: string; body: string; glyph: React.ReactNode }[] = [
  {
    title: "Every action runs in a snapshot",
    body: "A shell command starts a Sandbox instance from the current snapshot and returns a new one; reading a file starts nothing. States are immutable, so any earlier state can be resumed.",
    glyph: (
      <>
        <rect x="4" y="6" width="16" height="12" rx="2" />
        <path d="M8 10h8M8 14h5" />
      </>
    ),
  },
  {
    title: "Fork only where it matters",
    body: "When the next action would edit or create a file, two more candidate actions are sampled. Each distinct one continues in its own fork, with at most three fork points on any path from the start.",
    glyph: (
      <>
        <path d="M4 12h5M9 12c3 0 3-6 6-6h5M9 12h11M9 12c3 0 3 6 6 6h5" />
        <circle cx="9" cy="12" r="1.8" />
      </>
    ),
  },
  {
    title: "Check, then prune",
    body: "With more than four branches alive, each patch runs against the repository's existing tests (chosen from the files it changed) and is scored by Nemotron 3 Super. Branches that break existing tests rank last.",
    glyph: (
      <>
        <path d="M4 7h10M4 12h16M4 17h10" />
        <path d="M17 5l3 4M20 5l-3 4" />
      </>
    ),
  },
  {
    title: "Submit one patch",
    body: "The selected patch prefers no regressions, then an explicit submit, then the judge's score. Only then is it graded with the task's hidden tests.",
    glyph: (
      <>
        <path d="M5 12.5l4.5 4.5L19 7.5" />
      </>
    ),
  },
];

export default function Method() {
  return (
    <section className="section method" id="method" aria-labelledby="method-title">
      <div className="wrap method-grid">
        <header className="section-head method-head">
          <p className="stamp">How it works</p>
          <h2 id="method-title">Snapshots make a failed attempt cheap to abandon.</h2>
          <p className="fine">
            Tasks come from SWE-bench Lite. Of 104 held-out pytest-based tasks, all 79 that grade correctly in this
            harness are covered: the first 40, drawn with a fixed seed proportionally by repository, then the remaining
            39. django and sympy use other test runners and are out of scope.
          </p>
        </header>
        <ol className="steps-list">
          {STEPS.map((s, i) => (
            <li key={s.title}>
              <span className="step-no mono">{String(i + 1).padStart(2, "0")}</span>
              <svg className="step-glyph" viewBox="0 0 24 24" aria-hidden="true">{s.glyph}</svg>
              <div>
                <h3>{s.title}</h3>
                <p>{s.body}</p>
              </div>
            </li>
          ))}
        </ol>
      </div>
    </section>
  );
}
