"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { api, setToken } from "@/lib/api";
import { Button, Notice, inputClass } from "@/components/ui";

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
    <form onSubmit={submit} className="mt-20 space-y-5">
      <div className="space-y-2">
        <div className="inline-flex h-12 w-12 items-center justify-center rounded-2xl bg-[var(--accent)] text-2xl">
          <span aria-hidden className="text-[var(--accent-ink)]">◈</span>
        </div>
        <h1 className="text-3xl font-semibold tracking-tight">NexusCoach</h1>
        <p className="text-sm text-[var(--text-secondary)]">
          {mode === "login"
            ? "Sign in to your digital twin."
            : "Create an account and start building it."}
        </p>
      </div>

      <input
        type="email"
        required
        autoComplete="email"
        placeholder="Email"
        value={email}
        onChange={(e) => setEmail(e.target.value)}
        className={inputClass}
      />
      <input
        type="password"
        required
        minLength={mode === "register" ? 10 : undefined}
        autoComplete={mode === "login" ? "current-password" : "new-password"}
        placeholder={mode === "register" ? "Password (10+ characters)" : "Password"}
        value={password}
        onChange={(e) => setPassword(e.target.value)}
        className={inputClass}
      />

      {error && <Notice kind="error">{error}</Notice>}

      <Button type="submit" disabled={busy} full>
        {busy ? "…" : mode === "login" ? "Sign in" : "Create account"}
      </Button>

      <button
        type="button"
        onClick={() => {
          setMode(mode === "login" ? "register" : "login");
          setError(null);
        }}
        className="block w-full text-center text-sm text-[var(--text-secondary)]"
      >
        {mode === "login" ? "Need an account?" : "Already have an account?"}
      </button>
    </form>
  );
}
