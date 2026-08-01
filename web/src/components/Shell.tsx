"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { getToken } from "@/lib/api";

/** Single-path line icons, so the nav reads as icons without pulling in an icon set. */
const ICONS: Record<string, string> = {
  "/": "M4 13h7V4H4v9Zm0 7h7v-5H4v5Zm9 0h7v-9h-7v9Zm0-16v5h7V4h-7Z",
  "/body": "M12 4a2 2 0 1 0 0 4 2 2 0 0 0 0-4Zm-5 6h10M9 10v10M15 10v10",
  "/nutrition": "M12 20c3.5 0 6-2.7 6-6.2C18 9 14 4 12 3c-2 1-6 6-6 10.8C6 17.3 8.5 20 12 20Z",
  "/training": "M3 10v4M7 7v10M17 7v10M21 10v4M7 12h10",
  "/recovery": "M12 20s-7-4.3-7-9a4 4 0 0 1 7-2.6A4 4 0 0 1 19 11c0 4.7-7 9-7 9Z",
  "/coach": "M12 3l1.9 4.6L18.5 9l-4.6 1.9L12 15.5l-1.9-4.6L5.5 9l4.6-1.4L12 3ZM6 17l.9 2.1L9 20l-2.1.9L6 23l-.9-2.1L3 20l2.1-.9L6 17Z",
  "/integrations": "M9 3v6M15 3v6M7 9h10v4a5 5 0 0 1-10 0V9ZM12 18v3",
  "/profile": "M12 12a4 4 0 1 0 0-8 4 4 0 0 0 0 8ZM4 21a8 8 0 0 1 16 0",
};

// Labels match the page headings — abbreviated verbs read as a different app than the
// page you land on. Only the dashboard differs, and it has no heading of its own.
const NAV: [string, string][] = [
  ["/", "Home"],
  ["/body", "Body"],
  ["/nutrition", "Nutrition"],
  ["/training", "Training"],
  ["/recovery", "Recovery"],
  ["/coach", "Coach"],
  ["/integrations", "Sources"],
  ["/profile", "Profile"],
];

function Icon({ href }: { href: string }) {
  return (
    <svg viewBox="0 0 24 24" width="20" height="20" fill="none" aria-hidden>
      <path
        d={ICONS[href]}
        stroke="currentColor"
        strokeWidth="1.6"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

export default function Shell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const isLogin = pathname === "/login";

  useEffect(() => {
    // ponytail: the guard is a redirect, not route middleware — the API rejects every
    // unauthenticated call anyway, so this is UX, not the security boundary.
    if (!getToken() && !isLogin) router.replace("/login");
  }, [pathname, isLogin, router]);

  useEffect(() => {
    if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  }, []);

  if (isLogin) return <main className="mx-auto max-w-sm p-6">{children}</main>;

  return (
    <div className="mx-auto max-w-5xl px-4 pt-4 pb-32 sm:pb-10">
      <nav className="no-scrollbar mb-6 hidden gap-1 overflow-x-auto sm:flex">
        {NAV.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            aria-current={pathname === href ? "page" : undefined}
            className={`flex items-center gap-2 rounded-full px-4 py-2 text-sm whitespace-nowrap transition-colors ${
              pathname === href
                ? "bg-[var(--accent)] font-semibold text-[var(--accent-ink)]"
                : "bg-[var(--card)] text-[var(--text-secondary)]"
            }`}
          >
            <Icon href={href} />
            {label}
          </Link>
        ))}
      </nav>

      <main>{children}</main>

      {/* Mobile: a floating bar, as in the reference. Eight labelled items don't fit on a
          phone, so only the active one carries its label — the rest are icon-only. */}
      <nav className="fixed inset-x-3 bottom-3 z-10 sm:hidden">
        <div className="flex items-center gap-0.5 rounded-full border border-[var(--border)] bg-[var(--card)]/95 p-1.5 backdrop-blur">
          {NAV.map(([href, label]) => {
            const active = pathname === href;
            return (
              <Link
                key={href}
                href={href}
                aria-label={label}
                aria-current={active ? "page" : undefined}
                className={`flex min-w-0 items-center justify-center gap-1.5 rounded-full py-3.5 text-xs transition-colors ${
                  active
                    ? "shrink-0 bg-[var(--accent)] px-3.5 font-semibold text-[var(--accent-ink)]"
                    : "flex-1 text-[var(--text-secondary)]"
                }`}
              >
                <Icon href={href} />
                {active && label}
              </Link>
            );
          })}
        </div>
      </nav>
    </div>
  );
}
