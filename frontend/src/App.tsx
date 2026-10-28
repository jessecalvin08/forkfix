import { useEffect, useState } from "react";

import { Footer, Header } from "@/components/chrome";
import { getJSON, setParam, type RunIndex } from "@/data";
import { Method } from "@/sections/Method";
import { RealIssues } from "@/sections/RealIssues";
import { Replay, defaultTask } from "@/sections/Replay";
import { Walkthrough } from "@/sections/Walkthrough";
import { Evidence, Findings, Hero } from "@/sections/Results";

/** What the first paint looks like while the run index loads: the page's own shape, not a spinner. */
function Loading() {
  return (
    <div className="wrap pb-12 pt-10 md:pt-14" aria-busy="true">
      <p className="sr-only">Loading results</p>
      <div className="h-24 max-w-[20ch] rounded-sm bg-rule motion-safe:animate-pulse md:h-32" />
      <div className="mt-5 h-16 max-w-[62ch] rounded-sm bg-rule motion-safe:animate-pulse" />
      <div className="mt-8 space-y-5">
        {[0, 1, 2].map((i) => (
          <div key={i} className="h-14 rounded-sm bg-rule motion-safe:animate-pulse" />
        ))}
      </div>
    </div>
  );
}

export default function App() {
  const [index, setIndex] = useState<RunIndex | null>(null);
  const [failed, setFailed] = useState(false);
  const [retry, setRetry] = useState(0);
  const [task, setTask] = useState<string | null>(() => new URLSearchParams(window.location.search).get("task"));

  useEffect(() => {
    setFailed(false);
    getJSON<RunIndex>("/runs/index.json")
      .then(setIndex)
      .catch(() => setFailed(true));
  }, [retry]);

  // A shared ?task= link lands on the replay; a task id that no longer exists falls back to the default.
  const current = index ? (index.rows.some((r) => r.task === task) ? (task as string) : defaultTask(index)) : null;
  useEffect(() => {
    if (index && task && current === task) document.getElementById("replay")?.scrollIntoView();
    // only on the first paint of the index
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [index]);
  useEffect(() => setParam("task", task && current === task ? task : null), [task, current]);

  const pick = (t: string) => {
    setTask(t);
    document.getElementById("replay")?.scrollIntoView();
    requestAnimationFrame(() => document.getElementById("replay-detail")?.focus({ preventScroll: true }));
  };

  return (
    <div id="top">
      <a
        href="#result"
        className="sr-only focus:not-sr-only focus:absolute focus:left-4 focus:top-4 focus:z-50 focus:rounded-sm focus:bg-ink focus:px-3 focus:py-2 focus:text-paper"
      >
        Skip to the result
      </a>
      <Header />
      <main>
        {failed ? (
          <p role="alert" className="wrap py-24 text-muted">
            The run data did not load.{" "}
            <button type="button" className="underline underline-offset-4 hover:text-accent" onClick={() => setRetry((n) => n + 1)}>
              Try again
            </button>
          </p>
        ) : null}
        {!index && !failed ? <Loading /> : null}
        {index && current ? (
          <>
            <Hero index={index} />
            <Method />
            <Walkthrough />
            <Evidence index={index} onPick={pick} />
            <Findings index={index} />
            <Replay index={index} task={current} onTask={setTask} />
            <RealIssues />
          </>
        ) : null}
      </main>
      <Footer />
    </div>
  );
}
