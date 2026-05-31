import type { Metadata } from "next";
import Link from "next/link";
import "./globals.css";

export const metadata: Metadata = {
  title: "Trendscout – AI Trend Scouting (Schüco)",
  description:
    "AI-assisted trend scouting platform: discover, structure and assess trends.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en" className="h-full antialiased">
      <body className="min-h-full flex flex-col bg-white text-slate-900">
        <header className="border-b border-slate-200">
          <div className="mx-auto flex max-w-5xl items-center justify-between px-6 py-3.5">
            <Link href="/" className="flex items-baseline gap-2">
              <span className="text-[15px] font-semibold tracking-tight text-slate-900">
                Trendscout
              </span>
              <span className="text-xs font-normal text-slate-400">
                AI Trend Scouting · Schüco
              </span>
            </Link>
            <span className="text-[11px] uppercase tracking-wider text-slate-400">
              POC
            </span>
          </div>
        </header>
        <main className="mx-auto w-full max-w-5xl flex-1 px-6 py-10">
          {children}
        </main>
      </body>
    </html>
  );
}
