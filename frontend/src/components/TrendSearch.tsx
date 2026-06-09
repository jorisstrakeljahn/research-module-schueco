"use client";

import { Loader2, X } from "lucide-react";
import { useState } from "react";

import { startRun, type RunMode } from "@/lib/api";
import { useI18n } from "@/lib/i18n";

export default function TrendSearch({
  onStarted,
}: {
  onStarted?: (query: string) => void;
}) {
  const { t, lang } = useI18n();
  const [keywords, setKeywords] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [mode, setMode] = useState<RunMode>("deep_research");

  function addKeyword(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      const k = input.trim();
      if (!keywords.includes(k)) setKeywords([...keywords, k]);
      setInput("");
    }
  }

  async function search() {
    if (keywords.length === 0 || busy) return;
    setBusy(true);
    try {
      const { query } = await startRun(keywords, lang, mode);
      onStarted?.(query);
      setKeywords([]);
    } catch (e) {
      onStarted?.(`__error__:${String(e)}`);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="rounded-xl border border-border bg-surface p-5 shadow-sm">
      <h3 className="text-base font-medium text-fg">{t("search.title")}</h3>
      <p className="mt-0.5 text-sm text-muted">{t("search.subtitle")}</p>

      <div className="mt-4 flex flex-col gap-3 sm:flex-row">
        <input
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={addKeyword}
          placeholder={t("search.placeholder")}
          disabled={busy}
          className="flex-1 rounded-lg border border-border bg-bg px-4 py-2.5 text-sm text-fg placeholder-faint focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <button
          onClick={search}
          disabled={keywords.length === 0 || busy}
          className={`flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors ${
            keywords.length === 0 || busy
              ? "cursor-not-allowed bg-surface-2 text-faint"
              : "bg-primary text-white hover:bg-primary-bright"
          }`}
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {busy ? t("search.running") : t("search.button")}
        </button>
      </div>

      <div className="mt-3 flex items-center gap-3">
        <div className="inline-flex rounded-lg border border-border bg-bg p-0.5">
          {(["deep_research", "simple"] as RunMode[]).map((m) => (
            <button
              key={m}
              type="button"
              onClick={() => setMode(m)}
              disabled={busy}
              className={`rounded-md px-3 py-1 text-xs font-medium transition-colors ${
                mode === m
                  ? "bg-surface text-fg shadow-sm"
                  : "text-muted hover:text-fg"
              }`}
            >
              {t(m === "deep_research" ? "search.modeDeep" : "search.modeSimple")}
            </button>
          ))}
        </div>
        <span className="text-xs text-muted">
          {t(
            mode === "deep_research"
              ? "search.modeDeepHint"
              : "search.modeSimpleHint",
          )}
        </span>
      </div>

      {keywords.length > 0 && (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {keywords.map((k) => (
            <span
              key={k}
              className="flex items-center gap-1.5 rounded-full bg-primary/12 py-1 pl-3 pr-2 text-xs text-primary"
            >
              {k}
              <button
                onClick={() => setKeywords(keywords.filter((x) => x !== k))}
                disabled={busy}
                aria-label="remove"
                className="transition-colors hover:text-primary-bright"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}
