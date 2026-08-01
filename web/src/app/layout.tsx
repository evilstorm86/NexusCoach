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

export const viewport: Viewport = {
  themeColor: [
    { media: "(prefers-color-scheme: light)", color: "#f9f9f7" },
    { media: "(prefers-color-scheme: dark)", color: "#0d0d0d" },
  ],
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full">
        <Shell>{children}</Shell>
      </body>
    </html>
  );
}
