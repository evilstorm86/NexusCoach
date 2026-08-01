"use client";

import MetricPage from "@/components/MetricPage";
import { PAGES } from "@/lib/metrics";

export default function Page() {
  return <MetricPage title="Nutrition" metrics={PAGES.nutrition} />;
}
