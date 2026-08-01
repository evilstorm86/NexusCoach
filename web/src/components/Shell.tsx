"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { getToken } from "@/lib/api";

const NAV = [
  ["/", "Dashboard"],
  ["/body", "Body"],
  ["/nutrition", "Nutrition"],
  ["/training", "Training"],
  ["/recovery", "Recovery"],
  ["/coach", "AI Coach"],
  ["/integrations", "Integrations"],
  ["/profile", "Profile"],
];

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
    <div className="mx-auto max-w-5xl px-4 pb-24 pt-4 sm:pb-8">
      <nav className="mb-6 hidden gap-1 overflow-x-auto sm:flex">
        {NAV.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            className={`rounded-lg px-3 py-1.5 text-sm whitespace-nowrap ${
              pathname === href
                ? "bg-[var(--card)] text-[var(--text-primary)]"
                : "text-[var(--text-secondary)]"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>

      <main>{children}</main>

      {/* Mobile: the PWA is installed to a phone home screen, so navigation lives at the bottom. */}
      <nav className="fixed inset-x-0 bottom-0 flex overflow-x-auto border-t border-[var(--border)] bg-[var(--card)] sm:hidden">
        {NAV.map(([href, label]) => (
          <Link
            key={href}
            href={href}
            className={`flex-1 px-3 py-3 text-center text-xs whitespace-nowrap ${
              pathname === href ? "text-[var(--series-1)]" : "text-[var(--text-secondary)]"
            }`}
          >
            {label}
          </Link>
        ))}
      </nav>
    </div>
  );
}
