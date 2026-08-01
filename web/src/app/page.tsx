"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Me, type Series, type Summary } from "@/lib/api";
import { favourable, format, perWeek, spec } from "@/lib/metrics";
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
    // Every one of these reports its failure. Swallowing them made a broken API look
    // identical to an account with no data.
    const fail = (e: Error) => setError(e.message);
    api.get<Me>("/auth/me").then(setMe).catch(fail);
    api.get<Summary>("/analytics/summary").then(setSummary).catch(fail);
    api.get<Series>("/analytics/series?metric=weight&days=90").then(setWeight).catch(fail);
    api
      .get<{ prediction: Forecast }>("/analytics/predict?metric=weight&days_ahead=30")
      .then((p) => setForecast(p.prediction))
      .catch(fail);
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
            .map((m) => {
              const t = summary?.analysis[m]?.trend;
              return (
                <StatTile
                  key={m}
                  label={spec(m).label}
                  value={format(m, facts[m].latest)}
                  trend={t?.per_week}
                  favourable={t ? favourable(m, t.per_week) : null}
                  // The arrow describes the rate, so the rate is what sits beside it —
                  // it used to point at the measurement date.
                  detail={
                    t
                      ? `${perWeek(m, t.per_week)}/wk`
                      : new Date(facts[m].at).toLocaleDateString()
                  }
                />
              );
            })}
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

      {/* Hidden on an empty account: a card explaining there is nothing to project,
          directly under a card saying there is no data, is noise. */}
      {forecast && keys.length > 0 && (
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
