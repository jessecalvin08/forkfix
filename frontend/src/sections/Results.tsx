import { useMemo, useRef, useState } from "react";

import { Section } from "@/components/chrome";
import { ForkSketch } from "@/components/fork-sketch";
import {
  MODE_LABEL,
  ORDER,
  fmtP,
  fmtTokens,
  sortRows,
  taskName,
  usd,
  type IndexRow,
  type ModeName,
  type RunIndex,
} from "@/data";

const WHAT: Record<ModeName, string> = {
  branching: "forks before each edit",
  matched: "no forking, same compute",
  linear: "a single attempt",
};

const FILL: Record<ModeName, string> = { branching: "bg-accent", matched: "bg-ink", linear: "bg-mid" };

export function Hero({ index }: { index: RunIndex }) {
  const { totals: t, tasks } = index;
  return (
    <>
      <section id="result" aria-labelledby="result-title" className="pb-14 pt-10 md:pb-20 md:pt-16">
        <div className="wrap grid items-center gap-10 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)] lg:gap-14">
          <div>
            <h1
              id="result-title"
              className="max-w-[18ch] text-[clamp(2rem,1.2rem+3.2vw,3.4rem)] font-semibold leading-[1.05] tracking-[-0.035em]"
            >
              A coding agent that tries several fixes at once and keeps the one that works.
            </h1>
            <p className="mt-5 max-w-[54ch] text-[17px] text-muted">
              An AI agent fixing a bug usually makes one attempt and hopes. Forkfix saves a snapshot of the whole
              workspace before each edit, tries different edits side by side, runs the tests on each, and submits only
              the best.
            </p>
            <p className="mt-4 max-w-[54ch] text-[17px]">
              On {tasks} real bugs from open-source Python projects, the same small AI model fixed{" "}
              <strong className="font-semibold">{t.linear.solved}</strong> with one try and{" "}
              <strong className="font-semibold text-accent">{t.branching.solved}</strong> with Forkfix.
            </p>
            <p className="mt-6 flex flex-wrap gap-x-5 gap-y-1 text-sm">
              <a className="inline-flex min-h-9 items-center underline underline-offset-4 hover:text-accent" href="#evidence">
                See the evidence
              </a>
              <a className="inline-flex min-h-9 items-center underline underline-offset-4 hover:text-accent" href="#replay">
                Replay a real run
              </a>
            </p>
          </div>
          <figure>
            <ForkSketch />
            <figcaption className="mt-2 max-w-[44ch] text-sm text-muted">
              One run, simplified. Where the agent is about to change code, Forkfix forks the sandbox and follows
              several edits. Branches that fail the project&rsquo;s tests are dropped.
            </figcaption>
          </figure>
        </div>
      </section>
    </>
  );
}

export function Evidence({ index, onPick }: { index: RunIndex; onPick: (task: string) => void }) {
  const { totals: t, tasks, comparisons: c } = index;
  const rows = useMemo(() => sortRows(index.rows), [index.rows]);
  const [hover, setHover] = useState<IndexRow | null>(null);
  const [col, setCol] = useState(0);
  const cells = useRef<(HTMLButtonElement | null)[]>([]);
  const cost = (m: ModeName) => (t[m].estimated_usd == null ? "" : `costs about ${usd(t[m].estimated_usd)} to run`);

  // A mouse click opens the replay; a touch or pen tap pins the column so its name can be read first.
  const activate = (r: IndexRow, e: React.MouseEvent) => {
    const kind = (e.nativeEvent as PointerEvent).pointerType;
    if (kind === "touch" || kind === "pen") setHover(r);
    else onPick(r.task);
  };

  const onKey = (e: React.KeyboardEvent, i: number) => {
    const to = e.key === "ArrowRight" ? i + 1 : e.key === "ArrowLeft" ? i - 1 : e.key === "Home" ? 0 : e.key === "End" ? rows.length - 1 : null;
    if (to == null) return;
    e.preventDefault();
    const next = Math.max(0, Math.min(rows.length - 1, to));
    setCol(next);
    cells.current[next]?.focus();
  };

  const vars = { "--n": rows.length, "--c1": Math.ceil(rows.length / 4), "--c2": Math.ceil(rows.length / 2) } as React.CSSProperties;
  const outline = (r: IndexRow) => (hover?.task === r.task ? "outline outline-2 outline-offset-1 outline-ink" : "");

  return (
    <>
      <section id="evidence" aria-labelledby="evidence-title" className="border-t border-rule pb-14 pt-14 md:pb-20 md:pt-20">
        <div className="wrap">
          <h2 id="evidence-title" className="max-w-[26ch] text-[clamp(1.6rem,1.1rem+1.8vw,2.4rem)] font-semibold leading-[1.1] tracking-[-0.025em]">
            How well does it work?
          </h2>
          <p className="mt-3 max-w-[64ch] text-muted">
            We gave the same AI model {tasks} real bugs and let it work three ways. Each square below is one bug. A
            square is lit when the fix passed the project&rsquo;s own tests, which the agent never sees.
          </p>

          <figure className="mt-8" aria-label={`Each column is one of ${tasks} bugs`}>
            <div className="space-y-6">
              {ORDER.map((m, mi) => (
                <div key={m}>
                  <div className="mb-1.5 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-0.5">
                    <p className="flex flex-wrap items-baseline gap-x-2.5">
                      <span className="num text-[clamp(1.75rem,1.3rem+1.6vw,2.4rem)] font-semibold leading-none tracking-[-0.03em]">
                        {t[m].solved}
                        <span className="text-base font-normal text-muted"> of {tasks} fixed</span>
                      </span>
                      <span className="font-medium">{MODE_LABEL[m]}</span>
                      <span className="text-sm text-muted">{WHAT[m]}</span>
                    </p>
                    <p className="num font-mono text-sm text-muted">
                      {cost(m)}
                    </p>
                  </div>
                  {/* Only the first row is focusable: one stop per bug, and its label carries all three results. */}
                  <div className="strip" style={vars} aria-hidden={mi === 0 ? undefined : true} onMouseLeave={() => setHover(null)}>
                    {rows.map((r, i) => {
                      const on = r.modes[m].solved;
                      const look = `h-[22px] rounded-[2px] transition-colors md:h-6 ${on ? FILL[m] : "bg-rule"} ${outline(r)}`;
                      return mi === 0 ? (
                        <button
                          key={r.task}
                          ref={(el) => {
                            cells.current[i] = el;
                          }}
                          type="button"
                          tabIndex={i === col ? 0 : -1}
                          aria-label={`${taskName(r.task)}: ${ORDER.map((x) => `${MODE_LABEL[x].toLowerCase()} ${r.modes[x].solved ? "fixed it" : "did not fix it"}`).join(", ")}. Open the replay`}
                          onMouseEnter={() => setHover(r)}
                          onFocus={() => {
                            setHover(r);
                            setCol(i);
                          }}
                          onKeyDown={(e) => onKey(e, i)}
                          onClick={(e) => activate(r, e)}
                          className={look}
                        />
                      ) : (
                        <div key={r.task} onMouseEnter={() => setHover(r)} onClick={(e) => activate(r, e)} className={look} />
                      );
                    })}
                  </div>
                </div>
              ))}
            </div>

            <figcaption className="mt-4 space-y-1.5 text-sm text-muted">
              <p>
                The same bug sits in the same column in every row, and bugs Forkfix fixed come first. Click a square to
                replay that bug; arrow keys move between squares.
              </p>
              <p className="min-h-6 text-ink" aria-live="polite">
                {hover ? (
                  <>
                    <span className="font-mono">{taskName(hover.task)}</span>
                    <span className="text-muted">
                      {" · "}
                      {ORDER.map((m) => `${MODE_LABEL[m]} ${hover.modes[m].solved ? "fixed it" : "did not"}`).join(" · ")}
                      {" · "}
                    </span>
                    <button type="button" className="underline underline-offset-4 hover:text-accent" onClick={() => onPick(hover.task)}>
                      Open replay
                    </button>
                  </>
                ) : null}
              </p>
            </figcaption>
          </figure>
        </div>
      </section>
    </>
  );
}

/** One paired comparison: tasks only A solved, both solved, only B solved, all counted from the same rows. */
function Paired({ a, b, rows }: { a: ModeName; b: ModeName; rows: IndexRow[] }) {
  const onlyA = rows.filter((r) => r.modes[a].solved && !r.modes[b].solved).length;
  const onlyB = rows.filter((r) => !r.modes[a].solved && r.modes[b].solved).length;
  const both = rows.filter((r) => r.modes[a].solved && r.modes[b].solved).length;
  const total = onlyA + both + onlyB || 1;
  const seg = (n: number) => ({ width: `${(n / total) * 100}%` });
  return (
    <div>
      <div
        className="flex h-3 w-full gap-[2px]"
        role="img"
        aria-label={`${onlyA} only ${MODE_LABEL[a]}, ${both} both, ${onlyB} only ${MODE_LABEL[b]}`}
      >
        <span className="bg-accent" style={seg(onlyA)} />
        <span className="hatch" style={seg(both)} />
        <span className="bg-mid" style={seg(onlyB)} />
      </div>
      <dl className="num mt-2 flex flex-wrap gap-x-6 gap-y-1 font-mono text-sm">
        <div className="flex gap-1.5">
          <dt className="text-muted">only {MODE_LABEL[a]}</dt>
          <dd className="font-medium text-accent">{onlyA}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-muted">both</dt>
          <dd className="font-medium">{both}</dd>
        </div>
        <div className="flex gap-1.5">
          <dt className="text-muted">only {MODE_LABEL[b]}</dt>
          <dd className="font-medium">{onlyB}</dd>
        </div>
      </dl>
    </div>
  );
}

export function Findings({ index }: { index: RunIndex }) {
  const { totals: t, comparisons: c, forks, rows } = index;
  return (
    <Section
      id="findings-title"
      title="Which bugs did each way fix?"
      lede="Counting bug by bug: where Forkfix won, where the others did, and what the forks actually did."
    >
      <div className="divide-y divide-rule border-y border-rule">
        <article className="grid gap-4 py-7 lg:grid-cols-2 lg:gap-10">
          <div>
            <h3 className="font-semibold">Forkfix against one try</h3>
            <p className="mt-2 text-muted">
              Forkfix spent {(t.branching.tokens / t.linear.tokens).toFixed(1)}× the tokens and fixed bugs a single try
              did not. The gap is unlikely to be chance ({fmtP(c.branching_vs_linear.mcnemar_p)}).
            </p>
          </div>
          <Paired a="branching" b="linear" rows={rows} />
        </article>
        <article className="grid gap-4 py-7 lg:grid-cols-2 lg:gap-10">
          <div>
            <h3 className="font-semibold">Forkfix against independent tries</h3>
            <p className="mt-2 text-muted">
              Same compute, no forking. Forkfix is ahead, but the gap could still be chance ({fmtP(c.branching_vs_matched.mcnemar_p)}; the usual bar
              is 0.05), so this is not a settled win.
            </p>
          </div>
          <Paired a="branching" b="matched" rows={rows} />
        </article>
        <article className="grid gap-4 py-7 lg:grid-cols-2 lg:gap-10">
          <div>
            <h3 className="font-semibold">What the forks did</h3>
            <p className="mt-2 text-muted">
              A correct fix existed among the branches for {t.branching.any_candidate} bugs; Forkfix picked it for {t.branching.solved}.
            </p>
          </div>
          <dl className="num grid grid-cols-3 gap-4 font-mono">
            {[
              [forks.forks, `forks on ${forks.tasks_with_forks} tasks`],
              [forks.divergent_forks, "led somewhere different"],
              [forks.decisive_forks, "changed the outcome"],
            ].map(([n, l]) => (
              <div key={l}>
                <dd className="text-3xl font-semibold leading-none tracking-[-0.03em]">{n}</dd>
                <dt className="mt-1.5 font-sans text-sm text-muted">{l}</dt>
              </div>
            ))}
          </dl>
        </article>
      </div>
    </Section>
  );
}
