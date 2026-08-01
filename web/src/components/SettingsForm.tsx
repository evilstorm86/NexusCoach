"use client";

import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, Notice } from "@/components/ui";

type Setting = {
  name: string;
  label: string;
  help: string;
  secret: boolean;
  configured: boolean;
  source: "user" | "server" | "unset";
  value: string;
  updated_at: string | null;
};

const SOURCE_LABEL = {
  user: "your value",
  server: "server default",
  unset: "not set",
} as const;

export default function SettingsForm() {
  const [rows, setRows] = useState<Setting[] | null>(null);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [status, setStatus] = useState<{ kind: "error" | "ok"; text: string } | null>(null);
  const [busy, setBusy] = useState<string | null>(null);

  const load = () => api.get<Setting[]>("/settings").then(setRows);

  useEffect(() => {
    load().catch((e) => setStatus({ kind: "error", text: e.message }));
  }, []);

  async function run(name: string, action: () => Promise<unknown>, done: string) {
    setBusy(name);
    setStatus(null);
    try {
      await action();
      setDrafts((d) => ({ ...d, [name]: "" }));
      await load();
      setStatus({ kind: "ok", text: done });
    } catch (e) {
      setStatus({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(null);
    }
  }

  if (!rows) return <Card title="Settings">Loading…</Card>;

  return (
    <Card title="Settings">
      <p className="mb-4 text-xs text-[var(--text-muted)]">
        Your keys are stored encrypted and are never shown again after saving. Leave a
        field blank to use the server&apos;s own value.
      </p>

      <div className="space-y-5">
        {rows.map((row) => (
          <div key={row.name} className="space-y-1.5">
            <label htmlFor={row.name} className="block text-sm">
              {row.label}
            </label>
            <p className="text-xs text-[var(--text-muted)]">{row.help}</p>

            <div className="flex flex-wrap gap-2">
              <input
                id={row.name}
                type={row.secret ? "password" : "text"}
                autoComplete="off"
                value={drafts[row.name] ?? ""}
                onChange={(e) => setDrafts({ ...drafts, [row.name]: e.target.value })}
                placeholder={row.configured ? row.value : "Not set"}
                className="min-w-0 flex-1 rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
              />
              <Button
                disabled={busy === row.name || !(drafts[row.name] ?? "").trim()}
                onClick={() =>
                  run(
                    row.name,
                    () => api.put(`/settings/${row.name}`, { value: drafts[row.name] }),
                    `${row.label} saved.`,
                  )
                }
              >
                Save
              </Button>
              {row.source === "user" && (
                <Button
                  variant="quiet"
                  disabled={busy === row.name}
                  onClick={() =>
                    run(row.name, () => api.del(`/settings/${row.name}`), `${row.label} cleared.`)
                  }
                >
                  Clear
                </Button>
              )}
            </div>

            <p className="text-xs text-[var(--text-muted)]">
              {row.configured ? `Using ${SOURCE_LABEL[row.source]}` : "Not configured"}
              {row.secret && row.configured && row.source === "user" && ` (${row.value})`}
            </p>
          </div>
        ))}
      </div>

      {status && (
        <div className="mt-4">
          <Notice kind={status.kind}>{status.text}</Notice>
        </div>
      )}
    </Card>
  );
}
