import { GitCompare, GitFork, Scale } from "lucide-react";

import Features from "@/components/features";
import Stats from "@/components/stats";
import { MODES, MODE_LABEL, fmtP, fmtTokens, usd, type ModeName, type RunIndex } from "@/data";

const ORDER: ModeName[] = [...MODES].reverse(); // branching first

export function Results({ index }: { index: RunIndex }) {
  const { totals: t, comparisons: c, tasks, forks } = index;
  const cost = (m: ModeName) => (t[m].estimated_usd == null ? "" : ` · ${usd(t[m].estimated_usd)}`);

  return (
    <section id="result" aria-labelledby="result-title">
      <Stats
        level={1}
        title={
          <span id="result-title">
            Branching fixed {t.branching.solved} of {tasks}. Matched attempts fixed {t.matched.solved}. One attempt
            fixed {t.linear.solved}.
          </span>
        }
        subtitle={`${tasks} held-out SWE-bench Lite tasks, all with Nemotron 3 Nano, graded on hidden tests. Each cell shows tokens and list-price cost.`}
        cells={ORDER.map((m) => ({
          value: `${t[m].solved} of ${tasks}`,
          label: `${MODE_LABEL[m]} · ${fmtTokens(t[m].tokens)} tokens${cost(m)}`,
        }))}
      />
      <Features
        title="What the numbers say"
        subtitle="One model throughout; only the search changes."
        features={[
          {
            icon: Scale,
            title: "Against one attempt",
            description: `Branching alone solved ${c.branching_vs_linear.only_branching} tasks; one attempt alone solved ${c.branching_vs_linear.only_linear}. McNemar ${fmtP(c.branching_vs_linear.mcnemar_p)}. Branching spent ${(t.branching.tokens / t.linear.tokens).toFixed(1)}× the tokens.`,
          },
          {
            icon: GitCompare,
            title: "Against matched attempts",
            description: `With the same token budget, branching alone solved ${c.branching_vs_matched.only_branching} and matched attempts alone solved ${c.branching_vs_matched.only_matched}. McNemar ${fmtP(c.branching_vs_matched.mcnemar_p)}: the direction favours branching, but the gap is short of the 0.05 threshold.`,
          },
          {
            icon: GitFork,
            title: "What the forks did",
            description: `${forks.forks} forks across ${forks.tasks_with_forks} tasks; ${forks.divergent_forks} produced a different next action, and ${forks.decisive_forks} changed the outcome. A correct candidate existed on ${t.branching.any_candidate} tasks; ${t.branching.solved} were selected.`,
          },
        ]}
      />
    </section>
  );
}
