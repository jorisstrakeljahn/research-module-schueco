"use client";

import { ChevronDown, Loader2, X } from "lucide-react";
import { useEffect, useState } from "react";

import {
  fetchSearchCapabilities,
  startRun,
  type RunMode,
  type SearchCapabilities,
} from "@/lib/api";
import { useI18n } from "@/lib/i18n";
import {
  DEFAULT_SEARCH_PREFERENCES,
  readSearchPreferences,
  writeSearchPreferences,
  type ResearchDepth,
  type SearchRegion,
  type TopicGranularity,
} from "@/lib/search-preferences";

const REGIONS: SearchRegion[] = [
  "global",
  "europe",
  "dach",
  "north_america",
  "asia_pacific",
  "china",
];

const DEPTHS: ResearchDepth[] = ["quick", "standard", "deep"];
const FOCUS_SUGGESTIONS = {
  de: ["EPBD & Regulierung", "Kreislaufwirtschaft", "Digitale Gebäudehülle"],
  en: ["EPBD & regulation", "Circular economy", "Digital building envelope"],
};

export default function TrendSearch({
  onStarted,
  onError,
}: {
  onStarted?: (result: {
    run_id: number;
    query: string;
    language: string;
    mode: RunMode;
  }) => void;
  onError?: (error: string) => void;
}) {
  const { t, lang } = useI18n();
  const [query, setQuery] = useState("");
  const [keywords, setKeywords] = useState<string[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [depth, setDepth] = useState<ResearchDepth>(DEFAULT_SEARCH_PREFERENCES.depth);
  const [region, setRegion] = useState<SearchRegion>(DEFAULT_SEARCH_PREFERENCES.region);
  const [topicGranularity, setTopicGranularity] =
    useState<TopicGranularity>(DEFAULT_SEARCH_PREFERENCES.topicGranularity);
  const [sources, setSources] = useState<string[]>(DEFAULT_SEARCH_PREFERENCES.sources);
  const [capabilities, setCapabilities] = useState<SearchCapabilities | null>(null);

  useEffect(() => {
    async function loadPreferences() {
      const preferences = readSearchPreferences();
      try {
        const data = await fetchSearchCapabilities();
        setCapabilities(data);
        const enabled = data.sources
          .filter((source) => source.enabled)
          .map((source) => source.id);
        const allowed = new Set(enabled);
        const preferred = preferences.sources.filter((source) => allowed.has(source));
        // Sources that became available since the preferences were saved (e.g. a
        // freshly configured API key) are opted in automatically.
        const known = new Set(preferences.knownSources ?? preferences.sources);
        const newlyAvailable = enabled.filter((source) => !known.has(source));
        const selectedSources =
          preferred.length > 0
            ? [...new Set([...preferred, ...newlyAvailable])]
            : data.default_sources;
        setSources(selectedSources);
        writeSearchPreferences({
          ...preferences,
          sources: selectedSources,
          knownSources: enabled,
        });
      } catch {
        setCapabilities(null);
      }
      setDepth(preferences.depth);
      setRegion(preferences.region);
      setTopicGranularity(preferences.topicGranularity);
    }
    loadPreferences();
  }, []);

  function addKeyword(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" && input.trim()) {
      e.preventDefault();
      const k = input.trim();
      if (!keywords.includes(k)) setKeywords([...keywords, k]);
      setInput("");
    }
  }

  async function search() {
    if (!query.trim() || busy) return;
    const mode: RunMode = depth === "quick" ? "simple" : "deep_research";
    setBusy(true);
    try {
      const result = await startRun({
        query: query.trim(),
        keywords,
        language: lang,
        mode,
        depth,
        region,
        sources,
        topic_granularity: topicGranularity,
      });
      writeSearchPreferences({
        depth,
        region,
        sources,
        topicGranularity,
        knownSources: capabilities?.sources
          .filter((source) => source.enabled)
          .map((source) => source.id),
      });
      onStarted?.(result);
      setQuery("");
      setKeywords([]);
    } catch (e) {
      onError?.(String(e));
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
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") search();
          }}
          placeholder={t("search.queryPlaceholder")}
          disabled={busy}
          className="flex-1 rounded-lg border border-border bg-bg px-4 py-2.5 text-sm text-fg placeholder-faint focus:border-primary focus:outline-none focus:ring-1 focus:ring-primary"
        />
        <button
          onClick={search}
          disabled={!query.trim() || busy}
          className={`flex items-center justify-center gap-2 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors ${
            !query.trim() || busy
              ? "cursor-not-allowed bg-surface-2 text-faint"
              : "bg-primary text-white hover:bg-primary-bright"
          }`}
        >
          {busy && <Loader2 className="h-4 w-4 animate-spin" />}
          {busy ? t("search.running") : t("search.button")}
        </button>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-[1fr_1.35fr]">
        <label className="grid gap-1.5">
          <span className="text-xs font-medium text-muted">{t("search.region")}</span>
          <select
            value={region}
            onChange={(event) => setRegion(event.target.value as SearchRegion)}
            disabled={busy}
            className="h-10 rounded-lg border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
          >
            {REGIONS.map((value) => (
              <option key={value} value={value}>
                {t(`search.region.${value}`)}
              </option>
            ))}
          </select>
        </label>
        <div className="grid gap-1.5">
          <span className="text-xs font-medium text-muted">{t("search.depth")}</span>
          <div className="grid grid-cols-3 rounded-lg border border-border bg-bg p-0.5">
            {DEPTHS.map((value) => (
            <button
              key={value}
              type="button"
              onClick={() => setDepth(value)}
              disabled={busy}
              className={`rounded-md px-3 py-2 text-xs font-medium transition-colors ${
                depth === value
                  ? "bg-surface text-fg shadow-sm"
                  : "text-muted hover:text-fg"
              }`}
            >
              {t(`search.depth.${value}`)}
            </button>
          ))}
          </div>
          <p className="text-[11px] text-faint">{t(`search.depthHint.${depth}`)}</p>
        </div>
      </div>

      <details className="group mt-4 border-t border-border pt-3">
        <summary className="flex cursor-pointer list-none items-center justify-between text-xs font-medium text-muted">
          <span>{t("search.advanced")}</span>
          <ChevronDown className="h-4 w-4 transition-transform group-open:rotate-180" />
        </summary>
        <div className="mt-3 grid gap-4 md:grid-cols-2">
          <div>
            <label className="text-xs font-medium text-muted">{t("search.focusTerms")}</label>
            <input
              type="text"
              value={input}
              onChange={(event) => setInput(event.target.value)}
              onKeyDown={addKeyword}
              placeholder={t("search.focusPlaceholder")}
              disabled={busy}
              className="mt-1.5 h-10 w-full rounded-lg border border-border bg-bg px-3 text-sm text-fg outline-none focus:border-primary"
            />
            <p className="mt-1 text-[11px] text-faint">{t("search.focusHint")}</p>
            <div className="mt-2 flex flex-wrap gap-1.5">
              {FOCUS_SUGGESTIONS[lang].map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  disabled={busy || keywords.includes(suggestion)}
                  onClick={() => setKeywords((current) => [...current, suggestion])}
                  className="rounded-full border border-border px-2.5 py-1 text-[11px] text-muted transition-colors hover:border-primary hover:text-primary disabled:opacity-40"
                >
                  + {suggestion}
                </button>
              ))}
            </div>
          </div>
          <div>
            <p className="text-xs font-medium text-muted">{t("search.sources")}</p>
            <div className="mt-1.5 grid grid-cols-2 gap-2">
              {capabilities?.sources.map((source) => (
                <label
                  key={source.id}
                  className={`flex items-center gap-2 rounded-lg border px-3 py-2 text-xs ${
                    source.enabled ? "border-border text-fg" : "border-border/60 text-faint"
                  }`}
                >
                  <input
                    type="checkbox"
                    checked={sources.includes(source.id)}
                    disabled={
                      !source.enabled ||
                      busy ||
                      (sources.includes(source.id) && sources.length === 1)
                    }
                    onChange={(event) =>
                      setSources((current) =>
                        event.target.checked
                          ? [...current, source.id]
                          : current.filter((item) => item !== source.id),
                      )
                    }
                    className="accent-primary"
                  />
                  <span>{t(`search.source.${source.id}`)}</span>
                </label>
              ))}
            </div>
            <p className="mt-1 text-[11px] text-faint">
              {capabilities?.sources.some((source) => !source.enabled)
                ? t("search.sourcesUnavailable")
                : t("search.sourcesHint")}
            </p>
          </div>
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
      </details>
    </div>
  );
}
