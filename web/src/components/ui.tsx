"use client";

import type { ReactNode } from "react";

export function Card({
  title,
  action,
  children,
  className = "",
}: {
  title?: string;
  action?: ReactNode;
  children: ReactNode;
  className?: string;
}) {
  return (
    <section className={`rounded-3xl border border-[var(--border)] bg-[var(--card)] p-5 ${className}`}>
      {(title || action) && (
        <div className="mb-4 flex items-center justify-between gap-3">
          {title && <h2 className="text-base font-semibold">{title}</h2>}
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

/** Small pill label — the reference uses these for role, plan and status. */
export function Chip({
  children,
  tone = "muted",
}: {
  children: ReactNode;
  tone?: "muted" | "accent";
}) {
  const styles =
    tone === "accent"
      ? "bg-[var(--accent-wash)] text-[var(--accent)]"
      : "bg-[var(--raised)] text-[var(--text-secondary)]";
  return (
    <span className={`rounded-full px-2.5 py-1 text-[11px] font-medium tracking-wide ${styles}`}>
      {children}
    </span>
  );
}

export function StatTile({
  label,
  value,
  detail,
  trend,
}: {
  label: string;
  value: string;
  detail?: string;
  trend?: number | null;
}) {
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-xs text-[var(--text-secondary)]">{label}</div>
      <div className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</div>
      {detail && (
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
          {trend != null && trend !== 0 && (
            <span aria-hidden className="text-[var(--accent)]">
              {trend > 0 ? "▲" : "▼"}
            </span>
          )}
          {detail}
        </div>
      )}
    </div>
  );
}

export function Button({
  children,
  onClick,
  disabled,
  variant = "primary",
  type = "button",
  full,
}: {
  children: ReactNode;
  onClick?: () => void;
  disabled?: boolean;
  variant?: "primary" | "quiet" | "danger";
  type?: "button" | "submit";
  full?: boolean;
}) {
  const styles = {
    // Near-black ink on the bright accent — white on orange doesn't clear 4.5:1.
    primary: "bg-[var(--accent)] text-[var(--accent-ink)] font-semibold",
    quiet: "bg-[var(--raised)] text-[var(--text-primary)]",
    danger: "bg-[var(--raised)] text-[var(--critical)]",
  }[variant];
  // A dimmed accent reads as muddy-but-filled, i.e. still clickable. Disabled buttons
  // drop the fill entirely instead.
  const off = "bg-[var(--raised)] text-[var(--text-muted)] cursor-not-allowed";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-full px-5 py-2.5 text-sm transition-colors active:opacity-80 ${
        disabled ? off : styles
      } ${full ? "w-full" : ""}`}
    >
      {children}
    </button>
  );
}

/** Segmented pill control — the reference's Male/Female and range switchers. */
export function Segmented<T extends string | number>({
  options,
  value,
  onChange,
  label,
}: {
  options: { value: T; label: string }[];
  value: T;
  onChange: (v: T) => void;
  label: string;
}) {
  return (
    <div
      role="group"
      aria-label={label}
      className="inline-flex gap-1 rounded-full bg-[var(--raised)] p-1"
    >
      {options.map((o) => (
        <button
          key={String(o.value)}
          onClick={() => onChange(o.value)}
          aria-pressed={value === o.value}
          className={`rounded-full px-4 py-1.5 text-sm transition-colors ${
            value === o.value
              ? "bg-[var(--accent)] font-semibold text-[var(--accent-ink)]"
              : "text-[var(--text-secondary)]"
          }`}
        >
          {o.label}
        </button>
      ))}
    </div>
  );
}

export function Field({
  label,
  hint,
  children,
}: {
  label?: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-1.5">
      {label && <div className="text-sm">{label}</div>}
      {hint && <p className="text-xs text-[var(--text-muted)]">{hint}</p>}
      {children}
    </div>
  );
}

export const inputClass =
  "w-full rounded-2xl border border-[var(--border)] bg-[var(--raised)] px-4 py-3 text-sm outline-none focus:border-[var(--accent)]";

export function Notice({ kind, children }: { kind: "error" | "ok"; children: ReactNode }) {
  const color = kind === "error" ? "var(--critical)" : "var(--good)";
  return (
    <p role="status" className="text-sm" style={{ color }}>
      {kind === "error" ? "⚠ " : "✓ "}
      {children}
    </p>
  );
}
