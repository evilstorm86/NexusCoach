import type { Metadata, Viewport } from "next";
import Shell from "@/components/Shell";
import "./globals.css";

// ponytail: system font stack instead of next/font — one less network fetch on a phone,
// and the data-viz spec calls for the system sans anyway.
export const metadata: Metadata = {
  title: "NexusCoach",
  description: "Your digital twin: body, nutrition, training and recovery in one place.",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, title: "NexusCoach", statusBarStyle: "default" },
};

// Dark only — the app commits to one theme, so the chrome does too.
export const viewport: Viewport = { themeColor: "#0b0b0d" };

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
