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
  favourable,
}: {
  label: string;
  value: string;
  detail?: string;
  /** Rate of change. Drives the arrow — pass it only when `detail` describes that rate. */
  trend?: number | null;
  /** null when the metric has no better direction (heart rate, steps). */
  favourable?: boolean | null;
}) {
  const arrow = trend != null && trend !== 0;
  const colour =
    favourable == null ? "text-[var(--text-muted)]" : favourable ? "text-[var(--good)]" : "text-[var(--critical)]";
  return (
    <div className="rounded-2xl border border-[var(--border)] bg-[var(--card)] p-4">
      <div className="text-xs text-[var(--text-secondary)]">{label}</div>
      <div className="mt-1.5 text-2xl font-semibold tracking-tight">{value}</div>
      {detail && (
        <div className="mt-1.5 flex items-center gap-1.5 text-xs text-[var(--text-muted)]">
          {/* aria-hidden: the direction is already in the text beside it. */}
          {arrow && (
            <span aria-hidden className={colour}>
              {trend! > 0 ? "▲" : "▼"}
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
  // Disabled must differ from `quiet` in more than a shade of text: same background as
  // an enabled secondary button plus a dimmer word is indistinguishable. Outline only.
  const off =
    "border border-dashed border-[var(--border)] text-[var(--text-muted)] opacity-70 cursor-not-allowed";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`rounded-full px-5 py-3 text-sm transition-colors active:opacity-80 ${
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
          className={`rounded-full px-4 py-2.5 text-sm transition-colors ${
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

export const inputClass =
  "w-full rounded-2xl border border-[var(--border)] bg-[var(--raised)] px-4 py-3 text-sm outline-none focus:ring-2 focus:ring-[var(--accent)]";

export function Notice({ kind, children }: { kind: "error" | "ok"; children: ReactNode }) {
  const color = kind === "error" ? "var(--critical)" : "var(--good)";
  return (
    // Errors interrupt; confirmations wait their turn.
    <p role={kind === "error" ? "alert" : "status"} className="text-sm" style={{ color }}>
      {kind === "error" ? "⚠ " : "✓ "}
      {children}
    </p>
  );
}
