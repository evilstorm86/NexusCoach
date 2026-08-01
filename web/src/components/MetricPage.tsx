"use client";

import { useEffect, useState } from "react";
import { api, type Series, type Summary } from "@/lib/api";
import { favourable, format, perWeek, spec } from "@/lib/metrics";
import TrendChart from "./TrendChart";
import { Button, Card, Chip, Notice, Segmented, StatTile } from "./ui";

const RANGES = [
  { value: 30, label: "30d" },
  { value: 90, label: "90d" },
  { value: 365, label: "1y" },
];

/**
 * A fetch tagged with the request it answers. Comparing `key` to the current request is
 * what distinguishes "still loading" from "loaded" from "failed" — without it a stale
 * error outlives the failure and a failed fetch shows a spinner forever.
 */
type Load<T> = { key: string; data?: T; error?: string };

/** Shared by Body / Nutrition / Training / Recovery — same job, different metric list. */
export default function MetricPage({ title, metrics }: { title: string; metrics: string[] }) {
  const [selected, setSelected] = useState(metrics[0]);
  const [days, setDays] = useState(90);
  const [attempt, setAttempt] = useState(0);
  const [summary, setSummary] = useState<Load<Summary>>({ key: "" });
  const [chart, setChart] = useState<Load<Series>>({ key: "" });

  const summaryKey = String(days);
  const chartKey = `${selected}|${days}|${attempt}`;

  useEffect(() => {
    let live = true;
    const key = summaryKey;
    api
      .get<Summary>(`/analytics/summary?days=${days}`)
      .then((data) => live && setSummary({ key, data }))
      .catch((e) => live && setSummary({ key, error: e.message }));
    return () => {
      live = false;
    };
  }, [summaryKey, days]);

  useEffect(() => {
    let live = true;
    const key = chartKey;
    api
      .get<Series>(`/analytics/series?metric=${selected}&days=${days}`)
      .then((data) => live && setChart({ key, data }))
      .catch((e) => live && setChart({ key, error: e.message }));
    return () => {
      live = false;
    };
  }, [chartKey, selected, days]);

  const summaryReady = summary.key === summaryKey;
  const chartReady = chart.key === chartKey;
  const facts = summaryReady ? summary.data : undefined;
  const shown = chartReady ? chart.data : undefined;
  const error = (chartReady && chart.error) || (summaryReady && summary.error) || null;

  const tiles = metrics.filter((m) => facts?.facts[m]);
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
            const t = facts!.analysis[m]?.trend;
            return (
              <StatTile
                key={m}
                label={spec(m).label}
                value={format(m, facts!.facts[m].latest)}
                trend={t?.per_week}
                favourable={t ? favourable(m, t.per_week) : null}
                detail={
                  t ? `${perWeek(m, t.per_week)}/wk` : `${facts!.facts[m].days_of_data} day(s) of data`
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
            className={`rounded-full px-4 py-2.5 text-sm whitespace-nowrap transition-colors ${
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
        action={trend ? <Chip tone="accent">{perWeek(selected, trend.per_week)}/week</Chip> : null}
      >
        {chartReady && chart.error ? (
          <div className="space-y-3 py-8 text-center">
            <p className="text-sm text-[var(--text-secondary)]">
              Couldn&apos;t load {spec(selected).label.toLowerCase()}.
            </p>
            <Button variant="quiet" onClick={() => setAttempt((n) => n + 1)}>
              Try again
            </Button>
          </div>
        ) : shown ? (
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
