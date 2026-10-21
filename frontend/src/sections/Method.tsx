import ProcessSteps, { type Step } from "@/components/process-steps";
import { SectionIntro } from "@/components/section-intro";

const STEPS: Step[] = [
  {
    title: "Every action runs in a snapshot",
    description:
      "A shell command starts a Sandbox instance from the current snapshot and returns a new one; reading a file starts nothing. States are immutable, so any earlier state can be resumed.",
  },
  {
    title: "Fork only where it matters",
    description:
      "When the next action would edit or create a file, two more candidate actions are sampled. Each distinct one continues in its own fork, with at most three fork points on any path from the start.",
  },
  {
    title: "Check, then prune",
    description:
      "With more than four branches alive, each patch runs against the repository's existing tests, chosen from the files it changed, and is scored by Nemotron 3 Super. Branches that break existing tests rank last.",
  },
  {
    title: "Submit one patch",
    description:
      "The selected patch prefers no regressions, then an explicit submit, then the judge's score. Only then is it graded with the task's hidden tests, which the agent and the judge never see.",
  },
];

export function Method() {
  return (
    <section id="method" aria-labelledby="method-title" className="py-12">
      <SectionIntro
        id="method-title"
        title="Snapshots make a failed attempt cheap to abandon"
        subtitle="Tasks come from SWE-bench Lite: all 79 pytest-based held-out tasks that grade correctly in this harness. django and sympy use other test runners and are out of scope."
      />
      <ProcessSteps steps={STEPS} />
    </section>
  );
}
