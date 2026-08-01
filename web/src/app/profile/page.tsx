"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken, type Me } from "@/lib/api";
import SettingsForm from "@/components/SettingsForm";
import { Button, Card, Chip } from "@/components/ui";

export default function ProfilePage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api.get<Me>("/auth/me").then(setMe).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-semibold tracking-tight">Profile</h1>

      <Card>
        <div className="flex items-center gap-4">
          <div className="flex h-14 w-14 items-center justify-center rounded-2xl bg-[var(--accent)] text-xl font-semibold text-[var(--accent-ink)]">
            {(me?.email ?? "?").slice(0, 1).toUpperCase()}
          </div>
          <div className="min-w-0">
            <p className="truncate text-base font-medium">{me?.email ?? "…"}</p>
            <div className="mt-1.5">{me && <Chip tone="accent">{me.role}</Chip>}</div>
          </div>
        </div>
      </Card>

      <SettingsForm />

      <Button
        variant="danger"
        onClick={() => {
          clearToken();
          router.replace("/login");
        }}
      >
        Sign out
      </Button>

      <p className="text-xs text-[var(--text-muted)]">
        NexusCoach analyses your own data and is not a medical device. It does not diagnose
        conditions or prescribe treatment. Talk to a clinician about anything health-related.
      </p>
    </div>
  );
}
