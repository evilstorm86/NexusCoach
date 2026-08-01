"use client";

import { useState } from "react";
import type { Point, Trend } from "@/lib/api";
import { format, spec } from "@/lib/metrics";

const W = 800;
const H = 240;
const PAD = { top: 16, right: 16, bottom: 28, left: 48 };

type Props = { metric: string; raw: Point[]; smoothed: Point[]; trend: Trend };

const day = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

/**
 * Daily readings as dots, the smoothed trend as the line. Two marks, not two hues:
 * the raw series is the substrate and wears muted ink, the trend carries the color.
 */
export default function TrendChart({ metric, raw, smoothed, trend }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const { label, unit } = spec(metric);

  if (raw.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-[var(--text-muted)]">
        No {label.toLowerCase()} readings yet.
      </p>
    );
  }

  const values = [...raw.map((p) => p.value), ...smoothed.map((p) => p.value)];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || Math.abs(max) || 1;
  const lo = min - span * 0.1;
  const hi = max + span * 0.1;

  const times = raw.map((p) => new Date(p.ts).getTime());
  const t0 = times[0];
  const t1 = times[times.length - 1];
  const x = (t: number) =>
    PAD.left + ((t - t0) / (t1 - t0 || 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) =>
    PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);

  const line = smoothed.map((p) => `${x(new Date(p.ts).getTime())},${y(p.value)}`).join(" ");
  const ticks = [lo, (lo + hi) / 2, hi];
  const active = hover === null ? null : raw[hover];

  return (
    <figure className="m-0">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="w-full touch-none"
        role="img"
        aria-label={`${label} over time`}
        onPointerLeave={() => setHover(null)}
        onPointerMove={(e) => {
          const box = e.currentTarget.getBoundingClientRect();
          const px = ((e.clientX - box.left) / box.width) * W;
          let nearest = 0;
          times.forEach((t, i) => {
            if (Math.abs(x(t) - px) < Math.abs(x(times[nearest]) - px)) nearest = i;
          });
          setHover(nearest);
        }}
      >
        {ticks.map((v) => (
          <g key={v}>
            <line
              x1={PAD.left}
              x2={W - PAD.right}
              y1={y(v)}
              y2={y(v)}
              stroke="var(--grid)"
              strokeWidth="1"
              vectorEffect="non-scaling-stroke"
            />
            <text x={PAD.left - 8} y={y(v) + 4} textAnchor="end" fontSize="11" fill="var(--text-muted)">
              {v.toFixed(spec(metric).decimals)}
            </text>
          </g>
        ))}

        <text x={PAD.left} y={H - 8} fontSize="11" fill="var(--text-muted)">
          {day(raw[0].ts)}
        </text>
        <text x={W - PAD.right} y={H - 8} textAnchor="end" fontSize="11" fill="var(--text-muted)">
          {day(raw[raw.length - 1].ts)}
        </text>

        {raw.map((p, i) => (
          <circle
            key={p.ts}
            cx={x(times[i])}
            cy={y(p.value)}
            r={hover === i ? 5 : 3.5}
            fill="var(--text-muted)"
            opacity={hover === i ? 1 : 0.55}
          />
        ))}

        <polyline
          points={line}
          fill="none"
          stroke="var(--series-1)"
          strokeWidth="2"
          strokeLinejoin="round"
          strokeLinecap="round"
          vectorEffect="non-scaling-stroke"
        />

        {active && (
          <line
            x1={x(new Date(active.ts).getTime())}
            x2={x(new Date(active.ts).getTime())}
            y1={PAD.top}
            y2={H - PAD.bottom}
            stroke="var(--axis)"
            strokeWidth="1"
            vectorEffect="non-scaling-stroke"
          />
        )}
      </svg>

      <figcaption className="flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]">
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-0.5 w-4 bg-[var(--series-1)]" aria-hidden />
          Trend
        </span>
        <span className="flex items-center gap-1.5">
          <span className="inline-block h-2 w-2 rounded-full bg-[var(--text-muted)]" aria-hidden />
          Daily reading
        </span>
        {active && (
          <span className="text-[var(--text-primary)]">
            {day(active.ts)}: {format(metric, active.value)}
          </span>
        )}
        {trend && (
          <span>
            {trend.per_week > 0 ? "+" : ""}
            {trend.per_week} {unit || "units"}/week over {trend.days} days (r²{" "}
            {trend.r_squared})
          </span>
        )}
      </figcaption>

      <details className="mt-2 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer">Table view</summary>
        <table className="mt-2 w-full max-w-sm tabular-nums">
          <thead>
            <tr className="text-left text-[var(--text-muted)]">
              <th className="font-normal">Date</th>
              <th className="font-normal">Reading</th>
            </tr>
          </thead>
          <tbody>
            {[...raw].reverse().map((p) => (
              <tr key={p.ts}>
                <td>{day(p.ts)}</td>
                <td>{format(metric, p.value)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </details>
    </figure>
  );
}
