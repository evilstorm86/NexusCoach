"use client";

import { useEffect, useState } from "react";
import { api, type Series, type Summary } from "@/lib/api";
import { format, perWeek, spec } from "@/lib/metrics";
import TrendChart from "./TrendChart";
import { Card, Chip, Notice, Segmented, StatTile } from "./ui";

const RANGES = [
  { value: 30, label: "30d" },
  { value: 90, label: "90d" },
  { value: 365, label: "1y" },
];

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
  const trend = shown?.analysis.trend;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{title}</h1>
        <Segmented options={RANGES} value={days} onChange={setDays} label="Time range" />
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      {tiles.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {tiles.map((m) => {
            const t = summary!.analysis[m]?.trend;
            return (
              <StatTile
                key={m}
                label={spec(m).label}
                value={format(m, summary!.facts[m].latest)}
                trend={t?.per_week}
                detail={
                  t ? `${perWeek(m, t.per_week)}/wk` : `${summary!.facts[m].days_of_data} day(s) of data`
                }
              />
            );
          })}
        </div>
      )}

      <div className="no-scrollbar -mx-4 flex gap-2 overflow-x-auto px-4">
        {metrics.map((m) => (
          <button
            key={m}
            onClick={() => setSelected(m)}
            aria-pressed={selected === m}
            className={`rounded-full px-4 py-2 text-sm whitespace-nowrap transition-colors ${
              selected === m
                ? "bg-[var(--accent)] font-semibold text-[var(--accent-ink)]"
                : "bg-[var(--card)] text-[var(--text-secondary)]"
            }`}
          >
            {spec(m).label}
          </button>
        ))}
      </div>

      <Card
        title={spec(selected).label}
        action={
          trend ? <Chip tone="accent">{perWeek(selected, trend.per_week)}/week</Chip> : null
        }
      >
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
