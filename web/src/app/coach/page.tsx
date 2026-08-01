"use client";

import { Card } from "@/components/ui";

export default function CoachPage() {
  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">AI Coach</h1>
      <Card>
        <p className="text-sm text-[var(--text-secondary)]">
          The coach arrives in the next milestone. It will read the same facts, analysis and
          predictions shown on the other pages — and keep those three apart in what it tells you.
        </p>
      </Card>
    </div>
  );
}
