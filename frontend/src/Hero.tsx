import { useEffect, useRef } from "react";

import TreeView, { nodeName } from "./TreeView";
import { defaultNode, fmtTokens, shortTask, stopWords } from "./tree";
import { fmtP, significant, useScrub, useTaskRun, usd } from "./shared";
import { MODES, MODE_LABEL, type ModeName, type RunIndex } from "./types";

interface Props {
  index: RunIndex;
  featured: string;
  onOpen: (task: string, node?: string) => void;
}

/**
 * The first screen: the claim on the left, and on the right the claim's evidence as it happened,
 * one real branching run that plays itself once when it scrolls into view.
 */
export default function Hero({ index, featured, onOpen }: Props) {
  const { totals, comparisons: cmp } = index;
  const { run, failed } = useTaskRun(featured);
  const mr = run?.modes.branching ?? null;
  const max = mr?.config.max_steps ?? 30;
  const { upTo, playing, play, scrub, restart } = useScrub(max, featured);
  const stage = useRef<HTMLDivElement>(null);
  const started = useRef(false);

  // Play once, the first time the stage is mostly on screen.
  useEffect(() => {
    const el = stage.current;
    if (!el || !mr || started.current) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting && !started.current) {
          started.current = true;
          restart();
          io.disconnect();
        }
      },
      { threshold: 0.5 },
    );
    io.observe(el);
    return () => io.disconnect();
    // restart is stable enough for a one-shot observer; mr gates when the stage has content.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mr]);

  const row = index.rows.find((r) => r.task === featured);
  const selected = mr ? (mr.selected ?? defaultNode(mr)) : null;
  const rate = (m: ModeName) => `${totals[m].solved}`;

  return (
    <section className="hero" aria-labelledby="hero-title">
      <div className="wrap hero-grid">
        <div className="hero-copy">
          <p className="stamp">Nebius Sandboxes · NVIDIA Nemotron 3 Nano · SWE-bench Lite</p>
          <h1 id="hero-title">Fork the sandbox before the edit. Keep the branch that works.</h1>
          <p className="lede">
            Forkfix snapshots the repository at every step. When the agent is about to change a file, it samples two
            alternatives, runs each in its own copy, and lets a judge prune the weakest. One patch is submitted.
          </p>

          <dl className="scoreboard" aria-label={`Bugs fixed out of ${index.tasks} held-out tasks`}>
            {[...MODES].reverse().map((m) => (
              <div key={m} className={`score${m === "branching" ? " is-lead" : ""}`}>
                <dt>{MODE_LABEL[m]}</dt>
                <dd>
                  <span className="score-n">{rate(m)}</span>
                  <span className="score-of"> / {index.tasks}</span>
                </dd>
                <dd className="score-cost">
                  {usd(totals[m].estimated_usd)} <span className="dim">· {fmtTokens(totals[m].tokens)} tokens</span>
                </dd>
              </div>
            ))}
          </dl>

          <p className="verdict-line">
            Against one attempt the gap is <strong>{significant(cmp.branching_vs_linear.mcnemar_p) ? "significant" : "not significant"}</strong>{" "}
            (p = {fmtP(cmp.branching_vs_linear.mcnemar_p)}). Against equal-token attempts it is{" "}
            <strong>{significant(cmp.branching_vs_matched.mcnemar_p) ? "significant" : "not yet significant"}</strong>{" "}
            (p = {fmtP(cmp.branching_vs_matched.mcnemar_p)}).
          </p>

          <div className="actions">
            <a className="btn btn-primary" href="#replay">
              Open the full replay
            </a>
            <a className="btn" href="#result">
              Read the numbers
            </a>
          </div>
        </div>

        <figure className="stage" ref={stage} aria-label="A branching run, replayed">
          <header className="stage-head">
            <div>
              <p className="stamp">Featured run · branching only</p>
              <p className="stage-task mono">{shortTask(featured)}</p>
            </div>
            <div className="stage-controls">
              <span className="stamp" aria-live="off">
                Step {upTo} / {max}
              </span>
              <button className="btn btn-sm" onClick={play} disabled={!mr}>
                {playing ? "Pause" : upTo >= max ? "Replay" : "Play"}
              </button>
            </div>
          </header>

          <div className="stage-body">
            {failed && <p className="empty">The run did not load. Reload the page to try again.</p>}
            {!failed && !mr && <div className="skeleton" aria-busy="true" aria-label="Loading the featured run" />}
            {mr && selected && (
              <div className="tree-scroll" tabIndex={0} role="region" aria-label="Featured branch tree, scrollable">
                <TreeView
                  compact
                  mode="branching"
                  run={mr}
                  upTo={upTo}
                  selected={selected}
                  onSelect={(id) => onOpen(featured, id)}
                />
              </div>
            )}
          </div>

          <label className="scrub">
            <span className="visually-hidden">Replay position</span>
            <input
              type="range"
              min={0}
              max={max}
              value={upTo}
              onChange={(e) => scrub(Number(e.target.value))}
              disabled={!mr}
            />
          </label>

          <figcaption className="stage-cap">
            {row && mr ? (
              <>
                Branching solved this one; {MODES.filter((m) => m !== "branching" && !row.modes[m].solved).length === 2
                  ? "one attempt and equal-token attempts did not"
                  : "not every other mode did"}
                . {mr.sandbox_runs} sandbox runs, {fmtTokens(mr.tokens)} tokens. Select a branch to open it in the replay.
              </>
            ) : (
              "Loading."
            )}
            {mr && selected && <span className="visually-hidden"> Submitted: {nodeName("branching", selected)}, {stopWords(mr.nodes.find((n) => n.id === selected)!, mr.candidates[selected]?.resolved ?? null)}.</span>}
          </figcaption>
        </figure>
      </div>
    </section>
  );
}
