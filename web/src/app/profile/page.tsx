"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { api, clearToken, type Me } from "@/lib/api";
import { Button, Card } from "@/components/ui";

export default function ProfilePage() {
  const router = useRouter();
  const [me, setMe] = useState<Me | null>(null);

  useEffect(() => {
    api.get<Me>("/auth/me").then(setMe).catch(() => {});
  }, []);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Profile</h1>

      <Card>
        <dl className="grid grid-cols-[auto_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-[var(--text-secondary)]">Email</dt>
          <dd>{me?.email ?? "…"}</dd>
          <dt className="text-[var(--text-secondary)]">Role</dt>
          <dd>{me?.role ?? "…"}</dd>
        </dl>
      </Card>

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
