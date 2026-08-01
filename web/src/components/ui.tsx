"use client";

import type { ReactNode } from "react";

export function Card({ title, children }: { title?: string; children: ReactNode }) {
  return (
    <section className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      {title && <h2 className="mb-3 text-sm font-semibold text-[var(--text-secondary)]">{title}</h2>}
      {children}
    </section>
  );
}

export function StatTile({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail?: string;
}) {
  return (
    <div className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-xs text-[var(--text-secondary)]">{label}</div>
      <div className="mt-1 text-2xl">{value}</div>
      {detail && <div className="mt-1 text-xs text-[var(--text-muted)]">{detail}</div>}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "quiet" | "danger";
  type?: "button" | "submit";
}) {
  const styles = {
    primary: "bg-[var(--series-1)] text-white",
    quiet: "border border-[var(--border)] text-[var(--text-primary)]",
    danger: "border border-[var(--border)] text-[var(--critical)]",
  }[variant];
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-lg px-3 py-2 text-sm disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  );
}

export function Notice({ kind, children }: { kind: "error" | "ok"; children: ReactNode }) {
  const color = kind === "error" ? "var(--critical)" : "var(--good)";
  return (
    <p role="status" className="text-sm" style={{ color }}>
      {kind === "error" ? "⚠ " : "✓ "}
      {children}
    </p>
  );
}
