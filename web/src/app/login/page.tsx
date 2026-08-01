"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { Button, Notice } from "@/components/ui";

export default function LoginPage() {
  const router = useRouter();
  const [mode, setMode] = useState<"login" | "register">("login");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setError(null);
    try {
      if (mode === "register") await api.post("/auth/register", { email, password });
      const { access_token } = await api.form<{ access_token: string }>("/auth/login", {
        username: email,
        password,
      });
      setToken(access_token);
      router.replace("/");
    } catch (err) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <form onSubmit={submit} className="mt-16 space-y-4">
      <h1 className="text-2xl font-semibold">NexusCoach</h1>
      <p className="text-sm text-[var(--text-secondary)]">
        {mode === "login" ? "Sign in to your digital twin." : "Create an account."}
      </p>

      <input
        type="email"
        required
        autoComplete="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
      />
      <input
        type="password"
        required
        minLength={mode === "register" ? 10 : undefined}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        placeholder={mode === "register" ? "Password (10+ characters)" : "Password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className="w-full rounded-lg border border-[var(--border)] bg-[var(--card)] px-3 py-2 text-sm"
      />

      {error && <Notice kind="error">{error}</Notice>}

      <Button type="submit" disabled={busy}>
        {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
      </Button>

      <button
        type="button"
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setError(null);
        }}
        className="block text-sm text-[var(--text-secondary)] underline"
      >
        {mode === "login" ? "Need an account?" : "Already have an account?"}
      </button>
    </form>
  );
}
