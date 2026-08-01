"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Me, type Series, type Summary } from "@/lib/api";
import { format, perWeek, spec } from "@/lib/metrics";
import TrendChart from "@/components/TrendChart";
import { Card, Chip, Notice, StatTile } from "@/components/ui";

type Forecast = {
  available: boolean;
  basis?: string;
  assumption?: string;
  value_in_days?: { days: number; value: number };
};

export default function Dashboard() {
  const [me, setMe] = useState<Me | null>(null);
  const [summary, setSummary] = useState<Summary | null>(null);
  const [weight, setWeight] = useState<Series | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Me>("/auth/me").then(setMe).catch(() => {});
    api.get<Summary>("/analytics/summary").then(setSummary).catch((e) => setError(e.message));
    api.get<Series>("/analytics/series?metric=weight&days=90").then(setWeight).catch(() => {});
    api
      .get<{ prediction: Forecast }>("/analytics/predict?metric=weight&days_ahead=30")
      .then((p) => setForecast(p.prediction))
      .catch(() => {});
  }, []);

  const facts = summary?.facts ?? {};
  const keys = Object.keys(facts);
  const headline = facts.weight;
  const weightTrend = summary?.analysis.weight?.trend;

  return (
    <div className="space-y-6">
      <header className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm text-[var(--text-secondary)]">Welcome back</p>
          <h1 className="text-2xl font-semibold tracking-tight">
            {me?.email.split("@")[0] ?? "…"}
          </h1>
        </div>
        <Link
          href="/coach"
          className="rounded-full bg-[var(--accent)] px-5 py-2.5 text-sm font-semibold text-[var(--accent-ink)]"
        >
          Ask coach
        </Link>
      </header>

      {error && <Notice kind="error">{error}</Notice>}

      {headline && (
        <Card className="bg-gradient-to-br from-[var(--accent-wash)] to-transparent">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="text-sm text-[var(--text-secondary)]">Weight</p>
              <p className="mt-1 text-5xl font-semibold tracking-tight">
                {format("weight", headline.latest)}
              </p>
              <p className="mt-2 text-xs text-[var(--text-muted)]">
                measured {new Date(headline.at).toLocaleDateString()}
              </p>
            </div>
            {weightTrend && (
              <Chip tone="accent">
                {weightTrend.per_week > 0 ? "▲" : "▼"} {perWeek("weight", weightTrend.per_week)}/week
              </Chip>
            )}
          </div>
        </Card>
      )}

      {summary && keys.length === 0 && (
        <Card>
          <p className="text-sm text-[var(--text-secondary)]">
            No data yet. Connect a device or upload a file on the{" "}
            <Link href="/integrations" className="text-[var(--accent)] underline">
              Sources
            </Link>{" "}
            page.
          </p>
        </Card>
      )}

      {keys.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {keys
            .filter((m) => m !== "weight")
            .map((m) => (
              <StatTile
                key={m}
                label={spec(m).label}
                value={format(m, facts[m].latest)}
                trend={summary?.analysis[m]?.trend?.per_week}
                detail={new Date(facts[m].at).toLocaleDateString()}
              />
            ))}
        </div>
      )}

      {weight && weight.facts.length > 0 && (
        <Card title="Trend">
          <TrendChart
            metric="weight"
            raw={weight.facts}
            smoothed={weight.analysis.smoothed}
            trend={weight.analysis.trend}
          />
        </Card>
      )}

      {forecast && (
        <Card title="Projection" action={<Chip>prediction</Chip>}>
          {forecast.available && forecast.value_in_days ? (
            <div className="space-y-1.5 text-sm">
              <p className="text-3xl font-semibold tracking-tight">
                {format("weight", forecast.value_in_days.value)}
              </p>
              <p className="text-[var(--text-secondary)]">
                in {forecast.value_in_days.days} days — {forecast.basis}
              </p>
              <p className="text-xs text-[var(--text-muted)]">
                Assumes {forecast.assumption}. Not a medical forecast.
              </p>
            </div>
          ) : (
            <p className="text-sm text-[var(--text-secondary)]">
              Not enough data to project a trend yet.
            </p>
          )}
        </Card>
      )}
    </div>
  );
}
