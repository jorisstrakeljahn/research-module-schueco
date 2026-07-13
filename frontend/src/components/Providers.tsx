"use client";

import { ThemeProvider } from "next-themes";

import GlobalSearchProgress from "@/components/GlobalSearchProgress";
import { I18nProvider } from "@/lib/i18n";
import { RunProgressProvider } from "@/lib/run-progress";

export default function Providers({ children }: { children: React.ReactNode }) {
  return (
    <ThemeProvider
      attribute="class"
      defaultTheme="system"
      enableSystem
      disableTransitionOnChange
    >
      <I18nProvider>
        <RunProgressProvider>
          {children}
          <GlobalSearchProgress />
        </RunProgressProvider>
      </I18nProvider>
    </ThemeProvider>
  );
}
