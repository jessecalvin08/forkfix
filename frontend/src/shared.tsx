import { useEffect, useRef, useState } from "react";

import type { TaskRun } from "./types";

export function ForkMark({ size = 20 }: { size?: number }) {
  return (
    <svg className="fork-mark" width={size} height={size} viewBox="0 0 20 20" aria-hidden="true">
      <path d="M3 10 H8 M8 10 C11 10 11 5 14 5 H17 M8 10 H17 M8 10 C11 10 11 15 14 15 H17" />
      <circle cx="8" cy="10" r="1.9" />
    </svg>
  );
}

export const usd = (value: number | null | undefined): string => (value == null ? "n/a" : `$${value.toFixed(2)}`);

export const fmtP = (p: number): string => (p < 0.001 ? "< 0.001" : p.toFixed(3));

export const significant = (p: number): boolean => p < 0.05;

export const prefersReducedMotion = (): boolean =>
  typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

const cache = new Map<string, TaskRun>();

/** One task's saved run, cached across the hero and the workbench. `failed` lets the UI say so. */
export function useTaskRun(task: string | null): { run: TaskRun | null; failed: boolean } {
  const [run, setRun] = useState<TaskRun | null>(task ? (cache.get(task) ?? null) : null);
  const [failed, setFailed] = useState(false);
  useEffect(() => {
    if (!task) return;
    setFailed(false);
    const hit = cache.get(task);
    if (hit) {
      setRun(hit);
      return;
    }
    let live = true;
    fetch(`/runs/${task}.json`, { cache: "no-cache" })
      .then((r) => (r.ok ? r.json() : Promise.reject(new Error(String(r.status)))))
      .then((data: TaskRun) => {
        cache.set(task, data);
        if (live) setRun(data);
      })
      .catch(() => live && setFailed(true));
    return () => {
      live = false;
    };
  }, [task]);
  return { run: run && run.task === task ? run : null, failed };
}

/**
 * Step scrubber state. `upTo` runs 0..max; `play` restarts from 0 when it is already at the end.
 * With reduced motion the replay never animates: it jumps to the end state.
 */
export function useScrub(max: number, resetKey: string) {
  const [upTo, setUpTo] = useState(max);
  const [playing, setPlaying] = useState(false);
  const reduced = useRef(prefersReducedMotion());

  useEffect(() => {
    setPlaying(false);
    setUpTo(max);
  }, [resetKey, max]);

  useEffect(() => {
    if (!playing) return;
    if (upTo >= max) {
      setPlaying(false);
      return;
    }
    const t = window.setTimeout(() => setUpTo((s) => s + 1), 380);
    return () => window.clearTimeout(t);
  }, [playing, upTo, max]);

  const play = () => {
    if (reduced.current) return setUpTo(max);
    if (playing) return setPlaying(false);
    if (upTo >= max) setUpTo(0);
    setPlaying(true);
  };
  const scrub = (v: number) => {
    setPlaying(false);
    setUpTo(v);
  };
  const restart = () => {
    if (reduced.current) return setUpTo(max);
    setUpTo(0);
    setPlaying(true);
  };
  return { upTo, playing, play, scrub, restart };
}
