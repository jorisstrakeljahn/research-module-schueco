"use client";

import { type Lang, useI18n } from "@/lib/i18n";

const LANGS: { value: Lang; label: string }[] = [
  { value: "de", label: "DE" },
  { value: "en", label: "EN" },
];

export default function LanguageSwitch() {
  const { lang, setLang } = useI18n();

  return (
    <div className="flex gap-0.5 rounded-lg border border-border bg-surface p-0.5">
      {LANGS.map(({ value, label }) => {
        const active = lang === value;
        return (
          <button
            key={value}
            type="button"
            onClick={() => setLang(value)}
            aria-pressed={active}
            className={`flex-1 rounded-md py-1.5 text-xs font-medium transition-colors ${
              active ? "bg-surface-2 text-fg" : "text-faint hover:text-fg"
            }`}
          >
            {label}
          </button>
        );
      })}
    </div>
  );
}
