import type { Metadata } from "next";

import Providers from "@/components/Providers";
import Sidebar from "@/components/Sidebar";
import Toaster from "@/components/Toaster";
import "./globals.css";

export const metadata: Metadata = {
  title: "Schüco Trendradar – AI Trend Scouting",
  description:
    "AI-assisted trend scouting platform: discover, structure and assess trends.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="de" suppressHydrationWarning className="h-full antialiased">
      <body className="flex h-screen overflow-hidden bg-bg text-fg">
        <Providers>
          <Sidebar />
          <main className="flex min-h-0 flex-1 flex-col overflow-hidden">{children}</main>
          <Toaster />
        </Providers>
      </body>
    </html>
  );
}
