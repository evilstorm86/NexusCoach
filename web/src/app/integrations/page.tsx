"use client";

import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { Button, Card, Chip, Notice } from "@/components/ui";

type IngestResult = { received: number; created: number; updated: number };

function Upload({ label, path, accept }: { label: string; path: string; accept: string }) {
  const input = useRef<HTMLInputElement>(null);
  const [status, setStatus] = useState<{ kind: "error" | "ok"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);

  async function send(file: File) {
    setBusy(true);
    setStatus(null);
    try {
      const r = await api.upload<IngestResult>(path, file);
      setStatus({
        kind: "ok",
        text: `${r.created} new reading(s), ${r.updated} updated.`,
      });
    } catch (e) {
      setStatus({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
      if (input.current) input.current.value = "";
    }
  }

  const id = `upload-${path.replace(/\W+/g, "-")}`;
  return (
    <div className="space-y-2">
      <label htmlFor={id} className="block text-sm">
        {label}
      </label>
      <input
        id={id}
        ref={input}
        type="file"
        accept={accept}
        disabled={busy}
        onChange={(e) => e.target.files?.[0] && send(e.target.files[0])}
        className="block w-full text-sm text-[var(--text-secondary)] file:mr-3 file:rounded-full file:border file:border-[var(--border)] file:bg-transparent file:px-4 file:py-2.5 file:text-sm file:text-[var(--text-primary)]"
      />
      {busy && <p className="text-sm text-[var(--text-muted)]">Importing…</p>}
      {status && <Notice kind={status.kind}>{status.text}</Notice>}
    </div>
  );
}

type Withings = { connected: boolean; configured: boolean; last_sync: string | null };

export default function IntegrationsPage() {
  const [status, setStatus] = useState<{ kind: "error" | "ok"; text: string } | null>(null);
  const [busy, setBusy] = useState(false);
  const [withings, setWithings] = useState<Withings | null>(null);

  const loadStatus = () =>
    api.get<Withings>("/integrations/withings").then(setWithings).catch(() => {});

  useEffect(() => {
    loadStatus();
  }, []);

  async function run(action: () => Promise<string>) {
    setBusy(true);
    setStatus(null);
    try {
      setStatus({ kind: "ok", text: await action() });
    } catch (e) {
      setStatus({ kind: "error", text: (e as Error).message });
    } finally {
      setBusy(false);
      loadStatus();
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Sources</h1>

      <Card
        title="Withings"
        action={
          withings ? (
            <Chip tone={withings.connected ? "accent" : "muted"}>
              {withings.connected ? "Connected" : "Not connected"}
            </Chip>
          ) : null
        }
      >
        {withings && !withings.configured && (
          <p className="mb-3 text-sm text-[var(--text-secondary)]">
            No Withings credentials yet — add them under{" "}
            <Link href="/profile" className="text-[var(--accent)] underline">
              Profile → Settings
            </Link>
            .
          </p>
        )}
        {withings?.connected && (
          <p className="mb-3 text-sm text-[var(--text-muted)]">
            {withings.last_sync
              ? `Last synced ${new Date(withings.last_sync).toLocaleString()}`
              : "Never synced yet."}
          </p>
        )}

        <div className="flex flex-wrap gap-2">
          <Button
            disabled={busy || withings?.connected}
            onClick={() =>
              run(async () => {
                const { authorize_url } = await api.get<{ authorize_url: string }>(
                  "/integrations/withings/connect",
                );
                location.href = authorize_url;
                return "Redirecting to Withings…";
              })
            }
          >
            Connect
          </Button>
          <Button
            variant="quiet"
            disabled={busy || !withings?.connected}
            onClick={() =>
              run(async () => {
                const r = await api.post<IngestResult>("/integrations/withings/sync");
                return `${r.created} new reading(s), ${r.updated} updated.`;
              })
            }
          >
            Sync now
          </Button>
          <Button
            variant="danger"
            disabled={busy || !withings?.connected}
            onClick={() =>
              run(async () => {
                await api.del("/integrations/withings");
                return "Disconnected.";
              })
            }
          >
            Disconnect
          </Button>
        </div>
        {status && (
          <div className="mt-3">
            <Notice kind={status.kind}>{status.text}</Notice>
          </div>
        )}
      </Card>

      <Card title="File imports">
        <div className="space-y-5">
          <Upload
            label="Apple Health — export.zip or export.xml from the Health app"
            path="/imports/apple-health"
            accept=".zip,.xml"
          />
          <Upload
            label="CSV — columns: ts, metric, value, unit"
            path="/imports/csv"
            accept=".csv,text/csv"
          />
        </div>
      </Card>

      <Card title="Android Health Connect">
        <p className="text-sm text-[var(--text-secondary)]">
          Health Connect has no export file — data is read on-device through the SDK and posted
          to <code>/metrics</code> by the Android client.
        </p>
      </Card>
    </div>
  );
}
