"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { api, type Series, type Summary } from "@/lib/api";
import { format, spec } from "@/lib/metrics";
import TrendChart from "@/components/TrendChart";
import { Card, Notice, StatTile } from "@/components/ui";

type Forecast = {
  available: boolean;
  reason?: string;
  basis?: string;
  assumption?: string;
  value_in_days?: { days: number; value: number };
};

export default function Dashboard() {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [weight, setWeight] = useState<Series | null>(null);
  const [forecast, setForecast] = useState<Forecast | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.get<Summary>("/analytics/summary").then(setSummary).catch((e) => setError(e.message));
    api.get<Series>("/analytics/series?metric=weight&days=90").then(setWeight).catch(() => {});
    api
      .get<{ prediction: Forecast }>("/analytics/predict?metric=weight&days_ahead=30")
      .then((p) => setForecast(p.prediction))
      .catch(() => {});
  }, []);

  const facts = summary?.facts ?? {};
  const keys = Object.keys(facts);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Dashboard</h1>
      {error && <Notice kind="error">{error}</Notice>}

      {summary && keys.length === 0 && (
        <Card>
          <p className="text-sm text-[var(--text-secondary)]">
            No data yet. Connect a device or upload a file on the{" "}
            <Link href="/integrations" className="underline">
              Integrations
            </Link>{" "}
            page.
          </p>
        </Card>
      )}

      {keys.length > 0 && (
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-4">
          {keys.map((m) => (
            <StatTile
              key={m}
              label={spec(m).label}
              value={format(m, facts[m].latest)}
              detail={new Date(facts[m].at).toLocaleDateString()}
            />
          ))}
        </div>
      )}

      {weight && weight.facts.length > 0 && (
        <Card title="Weight">
          <TrendChart
            metric="weight"
            raw={weight.facts}
            smoothed={weight.analysis.smoothed}
            trend={weight.analysis.trend}
          />
        </Card>
      )}

      {forecast && (
        <Card title="Projection">
          {forecast.available && forecast.value_in_days ? (
            <div className="space-y-1 text-sm">
              <p className="text-lg">
                {format("weight", forecast.value_in_days.value)} in {forecast.value_in_days.days} days
              </p>
              <p className="text-[var(--text-secondary)]">{forecast.basis}</p>
              <p className="text-[var(--text-muted)]">
                Prediction — assumes {forecast.assumption}. Not a medical forecast.
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
