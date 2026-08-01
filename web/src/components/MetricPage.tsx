"use client";

import { useEffect, useState } from "react";
import { api, type Series, type Summary } from "@/lib/api";
import { format, spec } from "@/lib/metrics";
import TrendChart from "./TrendChart";
import { Card, Notice, StatTile } from "./ui";

const RANGES = [30, 90, 365];

/** Shared by Body / Nutrition / Training / Recovery — same job, different metric list. */
export default function MetricPage({ title, metrics }: { title: string; metrics: string[] }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [selected, setSelected] = useState(metrics[0]);
  const [days, setDays] = useState(90);
  const [series, setSeries] = useState<Series | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Summary>(`/analytics/summary?days=${days}`).then(setSummary).catch((e) => setError(e.message));
  }, [days]);

  useEffect(() => {
    api
      .get<Series>(`/analytics/series?metric=${selected}&days=${days}`)
      .then(setSeries)
      .catch((e) => setError(e.message));
  }, [selected, days]);

  const tiles = metrics.filter((m) => summary?.facts[m]);
  // Keep the old chart on a range change, but never show one metric's data under another's name.
  const shown = series?.metric === selected ? series : null;

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{title}</h1>
      {error && <Notice kind="error">{error}</Notice>}

      {tiles.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {tiles.map((m) => {
            const trend = summary!.analysis[m]?.trend;
            return (
              <StatTile
                key={m}
                label={spec(m).label}
                value={format(m, summary!.facts[m].latest)}
                detail={
                  trend
                    ? `${trend.per_week > 0 ? "+" : ""}${trend.per_week} ${spec(m).unit || ""}/wk`
                    : `${summary!.facts[m].days_of_data} day(s) of data`
                }
              />
            );
          })}
        </div>
      )}

      <div className="flex flex-wrap items-center gap-2">
        <select
          value={selected}
          onChange={(e) => setSelected(e.target.value)}
          className="rounded-lg border border-[var(--border)] bg-[var(--card)] px-2 py-1.5 text-sm"
          aria-label="Metric"
        >
          {metrics.map((m) => (
            <option key={m} value={m}>
              {spec(m).label}
            </option>
          ))}
        </select>
        <div className="flex gap-1">
          {RANGES.map((d) => (
            <button
              key={d}
              onClick={() => setDays(d)}
              aria-pressed={days === d}
              className={`rounded-lg px-2.5 py-1.5 text-sm ${
                days === d
                  ? "bg-[var(--series-1)] text-white"
                  : "border border-[var(--border)] text-[var(--text-secondary)]"
              }`}
            >
              {d}d
            </button>
          ))}
        </div>
      </div>

      <Card title={spec(selected).label}>
        {shown ? (
          <TrendChart
            metric={selected}
            raw={shown.facts}
            smoothed={shown.analysis.smoothed}
            trend={shown.analysis.trend}
          />
        ) : (
          <p className="py-10 text-center text-sm text-[var(--text-muted)]">Loading…</p>
        )}
      </Card>
    </div>
  );
}
