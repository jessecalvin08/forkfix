/**
 * One run, drawn: the agent is about to edit, Forkfix forks the sandbox, one branch fails its tests,
 * one is dropped, one is kept. The solid paths draw in once; reduced motion shows them finished.
 */
export function ForkSketch({ className = "" }: { className?: string }) {
  const draw = (i: number) => ({ pathLength: 1, className: "draw", style: { animationDelay: `${0.15 + i * 0.35}s` } });
  return (
    <svg
      viewBox="0 0 380 170"
      role="img"
      aria-label="A run forks at an edit into three branches. One fails its tests, one is dropped, and one is kept as the final patch."
      className={`w-full text-ink ${className}`}
    >
      <g fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round">
        <path d="M12 85 H80" {...draw(0)} />
        <path d="M80 85 C112 85 112 30 152 30 H206" {...draw(1)} />
        <path d="M80 85 C112 85 112 140 152 140 H206" strokeDasharray="2 6" />
        <path d="M80 85 H206" className="draw text-accent" pathLength={1} style={{ animationDelay: "0.85s" }} />
        <path d="M206 85 H316" className="draw text-accent" pathLength={1} style={{ animationDelay: "1.2s" }} />
      </g>
      <g fill="var(--color-paper)" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="85" r="5" />
        <circle cx="80" cy="85" r="5" fill="currentColor" />
        <circle cx="206" cy="30" r="5" />
        <circle cx="206" cy="140" r="5" />
        <circle cx="206" cy="85" r="5" className="text-accent" fill="currentColor" />
        <circle cx="316" cy="85" r="5" className="text-accent" fill="currentColor" />
      </g>
      <g className="font-sans" fontSize="12" fill="var(--color-muted)">
        <text x="4" y="48">
          snapshot saved,
        </text>
        <text x="4" y="64">
          about to edit
        </text>
        <text x="218" y="26">
          tests fail
        </text>
        <text x="218" y="161">
          judged weaker, dropped
        </text>
        <text x="316" y="108" textAnchor="middle" fill="var(--color-accent)" fontWeight="600">
          best patch
        </text>
      </g>
    </svg>
  );
}
