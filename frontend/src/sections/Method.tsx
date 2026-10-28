import { Section } from "@/components/chrome";

const STEPS = [
  {
    title: "It reads a bug report",
    body: "The kind developers write on GitHub: this code gives a wrong answer, please fix it.",
  },
  {
    title: "Before changing any code, it saves a snapshot",
    body: "Like a save point in a video game. The whole workspace is frozen exactly as it is, so the agent can always come back to it.",
  },
  {
    title: "It tries several different fixes at once",
    body: "Each attempt runs in its own copy of the workspace, so a mistake in one cannot break another.",
  },
  {
    title: "The project's own tests pick the winner",
    body: "Forkfix runs the tests on every attempt, drops the ones that fail or look weak, and submits the best one.",
  },
];

const DETAILS = [
  ["Snapshots", "A shell command starts a Sandbox instance from the current snapshot and returns a new one; reading a file starts nothing. States are immutable, so any earlier state can be resumed."],
  ["When it forks", "When the next action would edit or create a file, two more candidate actions are sampled. Each distinct one continues in its own fork, with at most three fork points on any path from the start."],
  ["How it prunes", "With more than four attempts alive, each patch runs against the repository's existing tests, chosen from the files it changed, and is scored by Nemotron 3 Super (the AI reviewer). Attempts that break existing tests rank last."],
  ["How it chooses", "The selected patch prefers no regressions, then an explicit submit, then the reviewer's score. Only then is it graded with the benchmark's hidden tests, which the agent and the reviewer never see."],
];

const TERMS = [
  ["Independent tries", "Several separate attempts with no forking, given exactly the compute Forkfix used on the same bug. The fair comparison."],
  ["Hidden tests", "The benchmark's own tests for the bug. They grade the final fix and are never shown to the agent."],
  ["p-value", "How likely a gap this size is by luck alone. Below 0.05 is the usual bar for calling it real."],
];

export function Method() {
  return (
    <Section
      id="method-title"
      anchor="method"
      title="How Forkfix fixes a bug"
      lede="An AI coding agent usually makes one attempt and hopes it was right. Forkfix lets it try several and keep the one that works."
    >
      <ol className="divide-y divide-rule border-y border-rule">
        {STEPS.map((s, i) => (
          <li key={s.title} className="grid grid-cols-[40px_minmax(0,1fr)] gap-x-2 py-6">
            <span className="num font-mono text-sm text-muted">{i + 1}</span>
            <div>
              <h3 className="font-semibold">{s.title}</h3>
              <p className="mt-1.5 max-w-[58ch] text-muted">{s.body}</p>
            </div>
          </li>
        ))}
      </ol>

      <details className="mt-6">
        <summary className="inline-flex min-h-11 cursor-pointer items-center text-sm underline underline-offset-4 hover:text-accent">
          Technical details and glossary
        </summary>
        <div className="mt-4 grid gap-10 lg:grid-cols-2">
          <dl className="space-y-4 text-sm">
            {DETAILS.map(([term, def]) => (
              <div key={term}>
                <dt className="font-medium">{term}</dt>
                <dd className="mt-0.5 text-muted">{def}</dd>
              </div>
            ))}
          </dl>
          <dl className="space-y-4 text-sm">
            {TERMS.map(([term, def]) => (
              <div key={term}>
                <dt className="font-medium">{term}</dt>
                <dd className="mt-0.5 text-muted">{def}</dd>
              </div>
            ))}
          </dl>
        </div>
      </details>
    </Section>
  );
}
