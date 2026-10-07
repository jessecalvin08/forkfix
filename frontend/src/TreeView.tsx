import type { KeyboardEvent } from "react";

import { layout, shortStop, stopWords } from "./tree";
import type { ModeName, ModeRun } from "./types";

const ROW = 28;
const PAD_X = 20;
const PAD_TOP = 34;
const LABEL_GAP = 18;

interface Props {
  mode: ModeName;
  run: ModeRun;
  upTo: number;
  selected: string;
  onSelect: (id: string) => void;
  /** Tighter steps and labels, for the hero where the tree shares the row with the claim. */
  compact?: boolean;
}

export function nodeName(mode: ModeName, id: string): string {
  if (mode === "branching") return `Branch ${id}`;
  if (mode === "matched") return `Attempt ${Number(id) + 1}`;
  return "Attempt";
}

export default function TreeView({ mode, run, upTo, selected, onSelect, compact = false }: Props) {
  const STEP = compact ? 13 : 20;
  const LABEL_W = compact ? 184 : 230;
  const { placed, rows } = layout(run);
  const steps = run.config.max_steps;
  const x = (step: number) => PAD_X + step * STEP;
  const y = (row: number) => PAD_TOP + row * ROW + ROW / 2;
  const labelX = x(steps) + LABEL_GAP;
  const width = labelX + LABEL_W;
  const height = PAD_TOP + rows * ROW + 8;
  const sel = placed.find((p) => p.node.id === selected);
  // During a replay the band waits for its branch to appear.
  const selectedRow = sel && (sel.node.born < upTo || upTo === steps) ? sel.row : undefined;

  const activate = (id: string) => (e: KeyboardEvent) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onSelect(id);
    }
  };

  return (
    <svg
      className="tree"
      viewBox={`0 0 ${width} ${height}`}
      width={width}
      height={height}
      role="group"
      aria-label={`${run.nodes.length} ${mode === "branching" ? (run.nodes.length === 1 ? "branch" : "branches") : run.nodes.length === 1 ? "attempt" : "attempts"} over ${steps} agent steps`}
    >
      {/* Step axis */}
      <g className="axis" aria-hidden="true">
        {Array.from({ length: steps / 5 + 1 }, (_, i) => i * 5).map((s) => (
          <g key={s}>
            <line x1={x(s)} x2={x(s)} y1={PAD_TOP - 6} y2={height - 8} className="gridline" />
            <text x={x(s)} y={PAD_TOP - 14} textAnchor="middle">{s}</text>
          </g>
        ))}
        <text x={labelX} y={PAD_TOP - 14} className="axis-title">OUTCOME</text>
      </g>

      {selectedRow !== undefined && (
        <rect className="row-band" x={0} y={PAD_TOP + selectedRow * ROW} width={width} height={ROW} />
      )}

      {placed.map(({ node, row, parentRow, fixAt, resolved, selected: isSubmitted }) => {
        const visible = node.born < upTo || (node.born === 0 && upTo > 0);
        if (!visible) return null;
        const end = Math.min(node.end, upTo);
        const done = node.end <= upTo;
        const leaf = node.stop !== "branched";
        // Colour arrives with the outcome: only once a passing patch below has finished.
        const onFixRoute = fixAt !== null && fixAt <= upTo;
        const cls = onFixRoute ? "seg fix" : node.stop === "pruned" ? "seg pruned" : "seg";
        const name = nodeName(mode, node.id);
        return (
          <g
            key={node.id}
            className={`node${node.id === selected ? " is-selected" : ""}`}
            role="button"
            tabIndex={0}
            aria-label={`${name}: steps ${node.born + 1} to ${node.end}, ${stopWords(node, resolved)}${isSubmitted ? ", submitted patch" : ""}`}
            aria-pressed={node.id === selected}
            onClick={() => onSelect(node.id)}
            onKeyDown={activate(node.id)}
          >
            <rect className="hit" x={x(node.born)} y={y(row) - ROW / 2} width={Math.max(x(end) - x(node.born), 8)} height={ROW} />
            {parentRow !== null && parentRow !== row && (
              <path
                className={cls}
                d={`M${x(node.born)},${y(parentRow)} V${y(row) - 8} Q${x(node.born)},${y(row)} ${x(node.born) + 8},${y(row)}`}
              />
            )}
            <line
              className={cls}
              x1={parentRow !== null && parentRow !== row ? x(node.born) + 8 : x(node.born)}
              x2={Math.max(x(end), x(node.born) + 8)}
              y1={y(row)}
              y2={y(row)}
            />
            {node.events
              // The last step sits under the end or fork mark.
              .filter((e) => e.step <= upTo && (e.step < node.end || !done))
              .map((e) => (
                <ToolMark key={e.step} tool={e.tool} cx={x(e.step)} cy={y(row)} fix={onFixRoute} />
              ))}
            {done && !leaf && <circle className="fork-dot" cx={x(node.end)} cy={y(row)} r={4.5} />}
            {done && leaf && <EndMark stop={node.stop} resolved={resolved} cx={x(node.end)} cy={y(row)} />}
            {done && leaf && (
              <text className={`row-label${resolved ? " fix" : ""}`} x={labelX} y={y(row) + 4}>
                <tspan className="row-id">{mode === "branching" ? node.id : name}</tspan>
                <tspan dx={10}>{shortStop(node, resolved)}</tspan>
                {isSubmitted && <tspan className="row-submitted" dx={8}>◂ submitted</tspan>}
              </text>
            )}
          </g>
        );
      })}

      {upTo < steps && (
        <line className="now" x1={x(upTo)} x2={x(upTo)} y1={PAD_TOP - 6} y2={height - 8} aria-hidden="true" />
      )}
    </svg>
  );
}

function ToolMark({ tool, cx, cy, fix }: { tool: string; cx: number; cy: number; fix: boolean }) {
  const cls = `mark${fix ? " fix" : ""}`;
  if (tool === "edit" || tool === "create") {
    return <rect className={`${cls} solid`} x={cx - 3.5} y={cy - 3.5} width={7} height={7} transform={`rotate(45 ${cx} ${cy})`} />;
  }
  if (tool === "view") return <circle className={`${cls} hollow`} cx={cx} cy={cy} r={2.6} />;
  if (tool === "bash") return <line className={cls} x1={cx} x2={cx} y1={cy - 5} y2={cy + 5} />;
  return null;
}

function EndMark({ stop, resolved, cx, cy }: { stop: string; resolved: boolean | null; cx: number; cy: number }) {
  if (resolved === true) {
    return (
      <g className="end fix">
        <rect x={cx - 7} y={cy - 7} width={14} height={14} rx={2} />
        <path d={`M${cx - 3.5},${cy} l2.5,2.8 l4.5,-5.6`} className="check" />
      </g>
    );
  }
  if (resolved === false) {
    return (
      <g className="end">
        <rect x={cx - 6} y={cy - 6} width={12} height={12} rx={2} className="hollow-end" />
        <path d={`M${cx - 2.5},${cy - 2.5} l5,5 M${cx + 2.5},${cy - 2.5} l-5,5`} className="cross" />
      </g>
    );
  }
  if (stop === "pruned") return <line className="end-bar" x1={cx} x2={cx} y1={cy - 7} y2={cy + 7} />;
  return <circle className="end-open" cx={cx} cy={cy} r={4.5} />;
}
