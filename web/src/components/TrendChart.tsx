"use client";

import { useEffect, useRef, useState } from "react";
import type { Point, Trend } from "@/lib/api";
import { format, perWeek, spec } from "@/lib/metrics";

const H = 220;
const PAD = { top: 14, right: 12, bottom: 26, left: 46 };

type Props = { metric: string; raw: Point[]; smoothed: Point[]; trend: Trend };

const day = (iso: string) =>
  new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });

/**
 * Round tick values to human numbers (82 / 84 / 86) instead of the padded extremes
 * (81.3 / 84.2 / 87.0). Tries increasing step sizes and takes the first that lands
 * 3–5 ticks inside the range.
 */
function ticksFor(lo: number, hi: number, decimals: number) {
  const range = hi - lo || 1;
  const magnitude = 10 ** Math.floor(Math.log10(range / 3));
  for (const multiple of [1, 2, 2.5, 5, 10]) {
    const step = multiple * magnitude;
    // A 2.5 step on a whole-number metric renders as 50/53/55/58 — evenly spaced marks
    // with unevenly spaced labels.
    if (decimals === 0 && !Number.isInteger(step)) continue;
    const out: number[] = [];
    for (let v = Math.ceil(lo / step) * step; v <= hi + 1e-9; v += step) {
      out.push(Number(v.toFixed(decimals + 2)));
    }
    if (out.length >= 3 && out.length <= 5) return out;
  }
  return [lo, (lo + hi) / 2, hi];
}

/**
 * Daily readings as dots, the smoothed trend as the line. Two marks, not two hues:
 * the raw series is the substrate and wears muted ink, the trend carries the color.
 *
 * Drawn at its real pixel size rather than scaled from a fixed viewBox — a fixed one
 * shrank the axis text to ~4px on a phone.
 */
export default function TrendChart({ metric, raw, smoothed, trend }: Props) {
  const [hover, setHover] = useState<number | null>(null);
  const [width, setWidth] = useState(0);
  const box = useRef<HTMLDivElement>(null);
  const { label, decimals } = spec(metric);

  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const observer = new ResizeObserver(([entry]) => setWidth(entry.contentRect.width));
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  if (raw.length === 0) {
    return (
      <p className="py-10 text-center text-sm text-[var(--text-muted)]">
        No readings for {label} yet.
      </p>
    );
  }

  const W = Math.max(width || 320, 240);
  const values = [...raw.map((p) => p.value), ...smoothed.map((p) => p.value)];
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = max - min || Math.abs(max) || 1;
  const lo = min - span * 0.1;
  const hi = max + span * 0.1;

  const times = raw.map((p) => new Date(p.ts).getTime());
  const t0 = times[0];
  const t1 = times[times.length - 1];
  const x = (t: number) => PAD.left + ((t - t0) / (t1 - t0 || 1)) * (W - PAD.left - PAD.right);
  const y = (v: number) => PAD.top + (1 - (v - lo) / (hi - lo)) * (H - PAD.top - PAD.bottom);

  const line = smoothed.map((p) => `${x(new Date(p.ts).getTime())},${y(p.value)}`).join(" ");
  const active = hover === null ? null : raw[hover];

  return (
    <figure className="m-0">
      <div ref={box}>
        <svg
          width={W}
          height={H}
          viewBox={`0 0 ${W} ${H}`}
          className="block max-w-full touch-none"
          role="img"
          aria-label={`${label} over time`}
          onPointerLeave={() => setHover(null)}
          onPointerMove={(e) => {
            const rect = e.currentTarget.getBoundingClientRect();
            const px = e.clientX - rect.left;
            let nearest = 0;
            times.forEach((t, i) => {
              if (Math.abs(x(t) - px) < Math.abs(x(times[nearest]) - px)) nearest = i;
            });
            setHover(nearest);
          }}
        >
          {ticksFor(lo, hi, decimals).map((v) => (
            <g key={v}>
              <line
                x1={PAD.left}
                x2={W - PAD.right}
                y1={y(v)}
                y2={y(v)}
                stroke="var(--grid)"
                strokeWidth="1"
              />
              <text
                x={PAD.left - 8}
                y={y(v) + 4}
                textAnchor="end"
                fontSize="11"
                fill="var(--text-muted)"
              >
                {v.toFixed(decimals)}
              </text>
            </g>
          ))}

          <text x={PAD.left} y={H - 6} fontSize="11" fill="var(--text-muted)">
            {day(raw[0].ts)}
          </text>
          <text x={W - PAD.right} y={H - 6} textAnchor="end" fontSize="11" fill="var(--text-muted)">
            {day(raw[raw.length - 1].ts)}
          </text>

          {raw.map((p, i) => (
            <circle
              key={p.ts}
              cx={x(times[i])}
              cy={y(p.value)}
              r={hover === i ? 4.5 : 3}
              fill="var(--text-muted)"
              opacity={hover === i ? 1 : 0.55}
            />
          ))}

          <polyline
            points={line}
            fill="none"
            stroke="var(--series-1)"
            strokeWidth="2.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />

          {active && (
            <line
              x1={x(new Date(active.ts).getTime())}
              x2={x(new Date(active.ts).getTime())}
              y1={PAD.top}
              y2={H - PAD.bottom}
              stroke="var(--axis)"
              strokeWidth="1"
            />
          )}
        </svg>
      </div>

      <figcaption className="mt-1 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-[var(--text-secondary)]">
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
            {perWeek(metric, trend.per_week)}/week over {Math.round(trend.days)} days (r²{" "}
            {trend.r_squared})
          </span>
        )}
      </figcaption>

      <details className="mt-2 text-xs text-[var(--text-secondary)]">
        <summary className="cursor-pointer py-2">Table view</summary>
        <table className="mt-1 w-full max-w-sm tabular-nums">
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
