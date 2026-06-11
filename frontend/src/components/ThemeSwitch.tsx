"use client";

import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { useSyncExternalStore } from "react";

import { useI18n } from "@/lib/i18n";

const emptySubscribe = () => () => {};

// `false` during SSR and the first client render (hydration-safe), `true` afterwards.
function useMounted() {
  return useSyncExternalStore(
    emptySubscribe,
    () => true,
    () => false,
  );
}

const OPTIONS = [
  { value: "light", icon: Sun, key: "theme.light" },
  { value: "dark", icon: Moon, key: "theme.dark" },
  { value: "system", icon: Monitor, key: "theme.system" },
] as const;

export default function ThemeSwitch() {
  const { theme, setTheme } = useTheme();
  const { t } = useI18n();
  // The active theme is only known on the client (next-themes resolves it from
  // storage/system after mount). Gate the active state on `mounted` so the first
  // client render matches the server HTML and hydration stays clean.
  const mounted = useMounted();

  return (
    <div className="flex gap-0.5 rounded-lg border border-border bg-surface p-0.5">
      {OPTIONS.map(({ value, icon: Icon, key }) => {
        const active = mounted && theme === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => setTheme(value)}
            aria-pressed={active}
            aria-label={t(key)}
            title={t(key)}
            className={`flex flex-1 items-center justify-center rounded-md py-1.5 transition-colors ${
              active ? "bg-surface-2 text-fg" : "text-faint hover:text-fg"
            }`}
          >
            <Icon className="h-4 w-4" />
          </button>
        );
      })}
    </div>
  );
}
