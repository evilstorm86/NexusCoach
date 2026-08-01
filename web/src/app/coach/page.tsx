"use client";

import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, Notice } from "@/components/ui";

type Turn = { role: "user" | "assistant"; content: string };

export default function CoachPage() {
  const [insight, setInsight] = useState<string | null>(null);
  const [turns, setTurns] = useState<Turn[]>([]);
  const [question, setQuestion] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const bottom = useRef<HTMLDivElement>(null);

  useEffect(() => {
    api
      .post<{ insight: string }>("/coach/insight")
      .then((r) => setInsight(r.insight))
      .catch((e) => setError(e.message));
  }, []);

  useEffect(() => {
    bottom.current?.scrollIntoView({ behavior: "smooth" });
  }, [turns, busy]);

  async function send(e: React.FormEvent) {
    e.preventDefault();
    const asked = question.trim();
    if (!asked || busy) return;

    setQuestion("");
    setError(null);
    setBusy(true);
    // The server keeps no thread — we resend the recent turns as context.
    const history = turns.slice(-10);
    setTurns([...turns, { role: "user", content: asked }]);
    try {
      const { answer } = await api.post<{ answer: string }>("/coach/ask", {
        question: asked,
        history,
      });
      setTurns((t) => [...t, { role: "assistant", content: answer }]);
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">AI Coach</h1>

      <Card title="Today">
        {insight ? (
          <p className="text-sm whitespace-pre-wrap">{insight}</p>
        ) : (
          <p className="text-sm text-[var(--text-muted)]">
            {error ? "No briefing yet." : "Preparing your briefing…"}
          </p>
        )}
      </Card>

      <div className="space-y-3">
        {turns.map((turn, i) => (
          <div
            key={i}
            className={`max-w-[85%] rounded-xl px-3 py-2 text-sm whitespace-pre-wrap ${
              turn.role === "user"
                ? "ml-auto bg-[var(--series-1)] text-white"
                : "border border-[var(--border)] bg-[var(--card)]"
            }`}
          >
            {turn.content}
          </div>
        ))}
        {busy && <p className="text-sm text-[var(--text-muted)]">Thinking…</p>}
        <div ref={bottom} />
      </div>

      {error && <Notice kind="error">{error}</Notice>}

      <form onSubmit={send} className="flex gap-2">
        <input
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
          placeholder="Ask about your data…"
          className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
        />
        <Button type="submit" disabled={busy || !question.trim()}>
          Ask
        </Button>
      </form>

      <p className="text-xs text-[var(--text-muted)]">
        The coach only sees your own measurements. It is not a clinician and does not
        diagnose conditions or recommend treatment.
      </p>
    </div>
  );
}
